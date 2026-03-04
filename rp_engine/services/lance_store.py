"""LanceDB vector store for exchange embeddings and card vectors.

Provides CoW-compatible vector storage with native versioning. Stores
embeddings alongside metadata for filtered ANN search. Replaces the
SQLite BLOB-based vector storage from vector_search.py.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa

logger = logging.getLogger(__name__)

# Schema for exchange vectors
EXCHANGE_SCHEMA = pa.schema([
    ("text", pa.string()),
    ("vector", pa.list_(pa.float32())),
    ("exchange_number", pa.int32()),
    ("rp_folder", pa.string()),
    ("branch", pa.string()),
    ("session_id", pa.string()),
    ("speaker", pa.string()),  # "user" or "assistant"
    ("in_story_timestamp", pa.string()),
])

# Schema for card vectors
CARD_SCHEMA = pa.schema([
    ("text", pa.string()),
    ("vector", pa.list_(pa.float32())),
    ("card_id", pa.string()),
    ("card_type", pa.string()),
    ("rp_folder", pa.string()),
    ("file_path", pa.string()),
    ("chunk_index", pa.int32()),
    ("total_chunks", pa.int32()),
])


@dataclass
class LanceSearchResult:
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class LanceStore:
    """LanceDB-backed vector store for exchanges and cards."""

    def __init__(
        self,
        db_path: str | Path,
        embed_fn: Callable | None = None,
        dimension: int = 384,
    ) -> None:
        self.db_path = Path(db_path)
        self._embed_fn = embed_fn
        self._dimension = dimension
        self._db = None
        self._exchange_table = None
        self._card_table = None

    async def initialize(self) -> None:
        """Open or create the LanceDB database and tables."""
        import lancedb

        self.db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.db_path))

        # Create or open tables
        if "exchange_vectors" not in self._db.table_names():
            # Create empty table with schema
            self._exchange_table = self._db.create_table(
                "exchange_vectors",
                schema=EXCHANGE_SCHEMA,
            )
        else:
            self._exchange_table = self._db.open_table("exchange_vectors")

        if "card_vectors" not in self._db.table_names():
            self._card_table = self._db.create_table(
                "card_vectors",
                schema=CARD_SCHEMA,
            )
        else:
            self._card_table = self._db.open_table("card_vectors")

        logger.info("LanceDB initialized at %s", self.db_path)

    async def embed_exchange(
        self,
        exchange_number: int,
        user_message: str,
        assistant_response: str,
        rp_folder: str,
        branch: str = "main",
        session_id: str | None = None,
        in_story_timestamp: str | None = None,
    ) -> int:
        """Chunk and embed an exchange (user + assistant). Returns chunk count."""
        if not self._embed_fn or not self._exchange_table:
            return 0

        from rp_engine.utils.text import chunk_text

        chunks_data = []

        # Embed user message
        user_chunks = chunk_text(user_message, chunk_size=500, overlap=50)
        for chunk in user_chunks:
            chunks_data.append({
                "text": chunk,
                "exchange_number": exchange_number,
                "rp_folder": rp_folder,
                "branch": branch,
                "session_id": session_id or "",
                "speaker": "user",
                "in_story_timestamp": in_story_timestamp or "",
            })

        # Embed assistant response
        asst_chunks = chunk_text(assistant_response, chunk_size=500, overlap=50)
        for chunk in asst_chunks:
            chunks_data.append({
                "text": chunk,
                "exchange_number": exchange_number,
                "rp_folder": rp_folder,
                "branch": branch,
                "session_id": session_id or "",
                "speaker": "assistant",
                "in_story_timestamp": in_story_timestamp or "",
            })

        if not chunks_data:
            return 0

        # Get embeddings
        try:
            texts = [c["text"] for c in chunks_data]
            embeddings = await self._embed_fn(texts)
        except Exception as e:
            logger.warning("Exchange embedding failed: %s", e)
            return 0

        # Build records with vectors
        for i, chunk_data in enumerate(chunks_data):
            chunk_data["vector"] = embeddings[i] if i < len(embeddings) else [0.0] * self._dimension

        self._exchange_table.add(chunks_data)
        return len(chunks_data)

    async def embed_card(
        self,
        card_id: str,
        content: str,
        rp_folder: str,
        card_type: str | None = None,
        file_path: str | None = None,
    ) -> int:
        """Chunk and embed a story card. Returns chunk count."""
        if not self._embed_fn or not self._card_table:
            return 0

        from rp_engine.utils.text import chunk_text

        # Remove existing vectors for this card
        try:
            self._card_table.delete(f'card_id = "{card_id}"')
        except Exception:
            pass  # Table may be empty

        chunks = chunk_text(content, chunk_size=1000, overlap=200)
        if not chunks:
            return 0

        try:
            embeddings = await self._embed_fn(chunks)
        except Exception as e:
            logger.warning("Card embedding failed for %s: %s", card_id, e)
            return 0

        records = []
        for i, chunk in enumerate(chunks):
            records.append({
                "text": chunk,
                "vector": embeddings[i] if i < len(embeddings) else [0.0] * self._dimension,
                "card_id": card_id,
                "card_type": card_type or "",
                "rp_folder": rp_folder,
                "file_path": file_path or "",
                "chunk_index": i,
                "total_chunks": len(chunks),
            })

        self._card_table.add(records)
        return len(records)

    async def search_exchanges(
        self,
        query_text: str,
        rp_folder: str,
        branch: str = "main",
        limit: int = 5,
        max_exchange: int | None = None,
    ) -> list[LanceSearchResult]:
        """Search exchange vectors for relevant past conversations."""
        if not self._embed_fn or not self._exchange_table:
            return []

        try:
            embeddings = await self._embed_fn([query_text])
            query_vec = embeddings[0]
        except Exception as e:
            logger.warning("Exchange search embedding failed: %s", e)
            return []

        try:
            query = (
                self._exchange_table.search(query_vec)
                .where(f'rp_folder = "{rp_folder}" AND branch = "{branch}"')
                .limit(limit)
            )

            results = query.to_list()
        except Exception as e:
            logger.warning("Exchange vector search failed: %s", e)
            return []

        search_results = []
        for row in results:
            if max_exchange and row.get("exchange_number", 0) > max_exchange:
                continue
            search_results.append(LanceSearchResult(
                text=row["text"],
                score=1.0 - row.get("_distance", 0),  # Lance returns distance
                metadata={
                    "exchange_number": row.get("exchange_number"),
                    "speaker": row.get("speaker"),
                    "session_id": row.get("session_id"),
                    "in_story_timestamp": row.get("in_story_timestamp"),
                },
            ))

        return search_results

    async def search_cards(
        self,
        query_text: str,
        rp_folder: str,
        limit: int = 10,
    ) -> list[LanceSearchResult]:
        """Search card vectors for relevant story cards."""
        if not self._embed_fn or not self._card_table:
            return []

        try:
            embeddings = await self._embed_fn([query_text])
            query_vec = embeddings[0]
        except Exception as e:
            logger.warning("Card search embedding failed: %s", e)
            return []

        try:
            results = (
                self._card_table.search(query_vec)
                .where(f'rp_folder = "{rp_folder}"')
                .limit(limit)
                .to_list()
            )
        except Exception as e:
            logger.warning("Card vector search failed: %s", e)
            return []

        return [
            LanceSearchResult(
                text=row["text"],
                score=1.0 - row.get("_distance", 0),
                metadata={
                    "card_id": row.get("card_id"),
                    "card_type": row.get("card_type"),
                    "file_path": row.get("file_path"),
                    "chunk_index": row.get("chunk_index"),
                },
            )
            for row in results
        ]

    async def rewind_exchanges(
        self,
        rp_folder: str,
        branch: str,
        after_exchange: int,
    ) -> None:
        """Delete exchange vectors after a given exchange number (for rewind)."""
        if not self._exchange_table:
            return
        try:
            self._exchange_table.delete(
                f'rp_folder = "{rp_folder}" AND branch = "{branch}" '
                f"AND exchange_number > {after_exchange}"
            )
        except Exception as e:
            logger.warning("Exchange vector rewind failed: %s", e)

    async def close(self) -> None:
        """Close LanceDB connection."""
        self._db = None
        self._exchange_table = None
        self._card_table = None
