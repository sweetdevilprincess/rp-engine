"""SQLite database with async write queue and migration support."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Write priority constants (lower = higher priority)
PRIORITY_EXCHANGE = 1
PRIORITY_ANALYSIS = 2
PRIORITY_REINDEX = 3


@dataclass(order=True)
class WriteItem:
    """A single database write operation queued for sequential execution."""

    priority: int
    timestamp: float = field(default_factory=time.monotonic)
    sql: str = field(compare=False, default="")
    params: list[Any] = field(compare=False, default_factory=list)
    many: bool = field(compare=False, default=False)
    result_future: asyncio.Future | None = field(compare=False, default=None)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)


class WriteQueue:
    """Single-consumer async write queue for all database mutations.

    All writes go through this queue, processed by one consumer task.
    Reads bypass the queue entirely (WAL snapshots allow concurrent reads).
    Failed writes requeue with exponential backoff.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self._queue: asyncio.PriorityQueue[WriteItem] = asyncio.PriorityQueue()
        self._consumer_task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the write queue consumer task."""
        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer_loop())
        logger.info("Write queue started")

    async def stop(self) -> None:
        """Stop the write queue, draining remaining items first."""
        if not self._running:
            return
        self._running = False
        # Put sentinel to wake up consumer
        sentinel = WriteItem(priority=999, sql="__STOP__")
        await self._queue.put(sentinel)
        if self._consumer_task:
            await self._consumer_task
        logger.info("Write queue stopped")

    async def enqueue(
        self,
        sql: str,
        params: list[Any] | None = None,
        priority: int = PRIORITY_ANALYSIS,
        many: bool = False,
    ) -> asyncio.Future:
        """Enqueue a write operation. Returns a Future with the result."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        item = WriteItem(
            priority=priority,
            sql=sql,
            params=params or [],
            many=many,
            result_future=future,
        )
        await self._queue.put(item)
        return future

    @property
    def size(self) -> int:
        return self._queue.qsize()

    async def _consumer_loop(self) -> None:
        """Process write items sequentially from the priority queue."""
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            if item.sql == "__STOP__":
                # Drain remaining items before stopping
                await self._drain()
                break

            await self._execute_write(item)

    async def _drain(self) -> None:
        """Process all remaining items in the queue."""
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item.sql == "__STOP__":
                continue
            await self._execute_write(item)

    async def _execute_write(self, item: WriteItem) -> None:
        """Execute a single write operation."""
        conn = self.db._write_connection
        try:
            if item.many:
                await conn.executemany(item.sql, item.params)
            else:
                cursor = await conn.execute(item.sql, item.params)
                lastrowid = cursor.lastrowid
            await conn.commit()
            if item.result_future and not item.result_future.done():
                item.result_future.set_result(lastrowid if not item.many else None)
        except Exception as e:
            if item.retry_count < item.max_retries:
                delay = 2 ** item.retry_count * 0.1
                logger.warning(
                    "Write failed (attempt %d/%d), retrying in %.1fs: %s",
                    item.retry_count + 1,
                    item.max_retries,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
                item.retry_count += 1
                item.timestamp = time.monotonic()
                await self._queue.put(item)
            else:
                logger.error("Write failed permanently after %d retries: %s", item.max_retries, e)
                if item.result_future and not item.result_future.done():
                    item.result_future.set_exception(e)


def _split_sql(sql: str) -> list[str]:
    """Split SQL text into individual statements, respecting BEGIN...END blocks.

    CREATE TRIGGER statements contain semicolons inside BEGIN...END that
    must not be treated as statement separators.
    """
    statements: list[str] = []
    current: list[str] = []
    in_block = False

    for line in sql.splitlines():
        stripped = line.strip()

        # Skip blank lines and comment-only lines at statement boundaries
        if not stripped or stripped.startswith("--"):
            if current:
                current.append(line)
            continue

        current.append(line)

        # Detect BEGIN (start of trigger body)
        upper = stripped.upper()
        if upper.endswith("BEGIN"):
            in_block = True
            continue

        if in_block:
            # END; closes the trigger block
            if upper.startswith("END"):
                in_block = False
                stmt = "\n".join(current).strip()
                # Remove trailing semicolon for execute()
                if stmt.endswith(";"):
                    stmt = stmt[:-1].strip()
                if stmt:
                    statements.append(stmt)
                current = []
            continue

        # Outside a block: semicolon terminates the statement
        if stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt.endswith(";"):
                stmt = stmt[:-1].strip()
            # Skip comments-only blocks
            if stmt and not all(
                line.strip().startswith("--") or not line.strip()
                for line in stmt.splitlines()
            ):
                statements.append(stmt)
            current = []

    # Handle any trailing statement without semicolon
    if current:
        stmt = "\n".join(current).strip()
        if stmt.endswith(";"):
            stmt = stmt[:-1].strip()
        if stmt and not all(
            line.strip().startswith("--") or not line.strip()
            for line in stmt.splitlines()
        ):
            statements.append(stmt)

    return statements


class Database:
    """Async SQLite database with WAL mode, migration support, and write queue."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path) if not isinstance(db_path, Path) else db_path
        self._read_connection: aiosqlite.Connection | None = None
        self._write_connection: aiosqlite.Connection | None = None
        self._write_queue: WriteQueue | None = None

    async def initialize(self) -> None:
        """Open connections, run migrations, start write queue."""
        is_memory = str(self.db_path) == ":memory:"

        # Create data directory (skip for in-memory DBs)
        if not is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # For in-memory DBs, use shared cache so both connections see same data
        connect_path = "file::memory:?cache=shared" if is_memory else str(self.db_path)
        connect_kwargs = {"uri": True} if is_memory else {}

        # Open read connection
        self._read_connection = await aiosqlite.connect(connect_path, **connect_kwargs)
        self._read_connection.row_factory = aiosqlite.Row
        await self._read_connection.execute("PRAGMA journal_mode=WAL")
        await self._read_connection.execute("PRAGMA foreign_keys=ON")

        # Open write connection
        self._write_connection = await aiosqlite.connect(connect_path, **connect_kwargs)
        self._write_connection.row_factory = aiosqlite.Row
        await self._write_connection.execute("PRAGMA journal_mode=WAL")
        await self._write_connection.execute("PRAGMA foreign_keys=ON")

        # Run migrations directly on write connection (before queue starts)
        await self._run_migrations()

        # Start write queue
        self._write_queue = WriteQueue(self)
        self._write_queue.start()

        logger.info("Database initialized: %s", self.db_path)

    async def close(self) -> None:
        """Stop write queue and close connections."""
        if self._write_queue:
            await self._write_queue.stop()
        if self._write_connection:
            await self._write_connection.close()
        if self._read_connection:
            await self._read_connection.close()
        logger.info("Database closed")

    # -- Read methods (bypass queue) --

    async def fetch_one(self, sql: str, params: list[Any] | None = None) -> dict | None:
        """Fetch a single row as a dict."""
        cursor = await self._read_connection.execute(sql, params or [])
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        """Fetch all rows as a list of dicts."""
        cursor = await self._read_connection.execute(sql, params or [])
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def fetch_val(self, sql: str, params: list[Any] | None = None) -> Any:
        """Fetch a single scalar value."""
        cursor = await self._read_connection.execute(sql, params or [])
        row = await cursor.fetchone()
        return row[0] if row else None

    # -- Write method (through queue) --

    async def enqueue_write(
        self,
        sql: str,
        params: list[Any] | None = None,
        priority: int = PRIORITY_ANALYSIS,
    ) -> asyncio.Future:
        """Enqueue a write operation. Returns a Future with lastrowid."""
        return await self._write_queue.enqueue(sql, params, priority)

    # -- Migrations --

    async def _run_migrations(self) -> None:
        """Apply unapplied SQL migration files."""
        conn = self._write_connection

        # Create migrations tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.commit()

        # Get already-applied migrations
        cursor = await conn.execute("SELECT name FROM _migrations")
        applied = {row[0] for row in await cursor.fetchall()}

        # Find and sort migration files
        if not MIGRATIONS_DIR.exists():
            return

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for migration_file in migration_files:
            if migration_file.name in applied:
                continue

            logger.info("Applying migration: %s", migration_file.name)
            sql_content = migration_file.read_text(encoding="utf-8")

            # Split SQL into individual statements, respecting BEGIN...END blocks
            # (triggers contain semicolons inside BEGIN...END that must not split)
            for stmt in _split_sql(sql_content):
                await conn.execute(stmt)

            # Record migration
            await conn.execute(
                "INSERT INTO _migrations (name) VALUES (?)",
                [migration_file.name],
            )
            await conn.commit()
            logger.info("Migration applied: %s", migration_file.name)

    # -- Health --

    async def health(self) -> dict:
        """Return database health info."""
        table_count = await self.fetch_val(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        journal_mode = await self.fetch_val("PRAGMA journal_mode")
        queue_size = self._write_queue.size if self._write_queue else 0
        return {
            "status": "ok",
            "tables": table_count,
            "journal_mode": journal_mode,
            "write_queue_size": queue_size,
        }
