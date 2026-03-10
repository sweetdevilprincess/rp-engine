"""Structured diagnostic logger — writes JSONL to disk with rotation + export."""

from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from rp_engine.config import DiagnosticConfig

logger = logging.getLogger(__name__)


class DiagnosticLogger:
    """Structured diagnostic logger that writes JSONL to disk.

    Always instantiated (part of the container), but short-circuits
    ``log()`` calls when ``config.enabled`` is False.
    """

    def __init__(self, config: DiagnosticConfig, data_dir: Path) -> None:
        self._config = config
        self._data_dir = data_dir
        self._diag_dir = data_dir / "diagnostics"
        self._archive_dir = self._diag_dir / "archive"
        self._current_file = self._diag_dir / "current.jsonl"
        self._file_handle: io.TextIOWrapper | None = None

        # Auto-generate reporter key if empty
        if not self._config.reporter_key:
            self._config.reporter_key = uuid.uuid4().hex[:12]

        # Ensure directories exist
        self._diag_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        # Purge old files on init
        if self._config.enabled:
            self._purge_old()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def config(self) -> DiagnosticConfig:
        return self._config

    def update_config(self, new_config: DiagnosticConfig) -> None:
        """Hot-update the config (e.g. from PUT /api/diagnostics)."""
        was_enabled = self._config.enabled
        self._config = new_config
        if not new_config.reporter_key:
            new_config.reporter_key = uuid.uuid4().hex[:12]
        if not new_config.enabled and was_enabled:
            self._close_handle()
        if new_config.enabled and not was_enabled:
            self._diag_dir.mkdir(parents=True, exist_ok=True)
            self._archive_dir.mkdir(parents=True, exist_ok=True)
            self._purge_old()

    def log(
        self,
        category: str,
        event: str,
        data: dict[str, Any],
        content: dict[str, Any] | None = None,
    ) -> None:
        """Write a structured log entry. No-op when disabled."""
        self._write_entry("info", category, event, data, content)

    def log_error(
        self,
        event: str,
        data: dict[str, Any],
        content: dict[str, Any] | None = None,
    ) -> None:
        """Write an error-level log entry."""
        self._write_entry("error", "error", event, data, content)

    def status(self) -> dict[str, Any]:
        """Return current diagnostic status."""
        file_size = 0
        entry_count = 0
        last_entry_ts: str | None = None

        if self._current_file.exists():
            file_size = self._current_file.stat().st_size
            # Count lines (entries)
            try:
                with open(self._current_file) as f:
                    for line in f:
                        entry_count += 1
                        stripped = line.strip()
                        if stripped:
                            last_entry_ts = stripped  # will parse last one
            except Exception:
                pass
            # Extract timestamp from last entry
            if last_entry_ts:
                try:
                    last_entry_ts = json.loads(last_entry_ts).get("ts")
                except Exception:
                    last_entry_ts = None

        archive_count = len(list(self._archive_dir.glob("*.jsonl")))

        return {
            "enabled": self._config.enabled,
            "level": self._config.level,
            "file_size_bytes": file_size,
            "entry_count": entry_count,
            "archive_count": archive_count,
            "last_entry_ts": last_entry_ts,
            "reporter_key": self._config.reporter_key,
            "auto_report": self._config.auto_report.model_dump(),
        }

    def clear(self) -> dict[str, int]:
        """Delete all log files. Returns count of files removed."""
        self._close_handle()
        removed = 0
        if self._current_file.exists():
            self._current_file.unlink()
            removed += 1
        for f in self._archive_dir.glob("*.jsonl"):
            f.unlink()
            removed += 1
        return {"files_removed": removed}

    def export_zip(self) -> bytes:
        """Create a zip of all log files and return as bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if self._current_file.exists():
                zf.write(self._current_file, "current.jsonl")
            for f in sorted(self._archive_dir.glob("*.jsonl")):
                zf.write(f, f"archive/{f.name}")
        return buf.getvalue()

    async def send_report(self, url: str | None = None) -> dict[str, Any]:
        """POST the zip to a webhook URL."""
        target = url or self._config.auto_report.url
        if not target:
            return {"ok": False, "error": "No webhook URL configured"}

        zip_bytes = self.export_zip()
        if len(zip_bytes) < 22:  # empty zip
            return {"ok": False, "error": "No log data to send"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    target,
                    content=zip_bytes,
                    headers={
                        "Content-Type": "application/zip",
                        "X-Reporter-Key": self._config.reporter_key,
                    },
                )
                return {
                    "ok": resp.status_code < 400,
                    "status_code": resp.status_code,
                    "reporter_key": self._config.reporter_key,
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_entry(
        self,
        level: str,
        category: str,
        event: str,
        data: dict[str, Any],
        content: dict[str, Any] | None = None,
    ) -> None:
        """Build and write a single JSONL entry. No-op when disabled."""
        if not self._config.enabled:
            return

        entry: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": level,
            "category": category,
            "event": event,
            "data": data,
        }
        if content is not None and self._config.level == "full":
            entry["content"] = content

        try:
            self._rotate_if_needed()
            handle = self._get_handle()
            handle.write(json.dumps(entry, default=str) + "\n")
            handle.flush()
        except Exception:
            logger.debug("Failed to write diagnostic log entry", exc_info=True)

    def _get_handle(self) -> io.TextIOWrapper:
        if self._file_handle is None or self._file_handle.closed:
            self._diag_dir.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(self._current_file, "a", encoding="utf-8")  # noqa: SIM115
        return self._file_handle

    def _close_handle(self) -> None:
        if self._file_handle is not None and not self._file_handle.closed:
            self._file_handle.close()
            self._file_handle = None

    def _rotate_if_needed(self) -> None:
        """Rotate current.jsonl if it exceeds max size."""
        if not self._current_file.exists():
            return
        size_mb = self._current_file.stat().st_size / (1024 * 1024)
        if size_mb < self._config.max_file_size_mb:
            return

        self._close_handle()
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        dest = self._archive_dir / f"log_{ts}.jsonl"
        self._current_file.rename(dest)

        # Enforce max_files limit
        archives = sorted(self._archive_dir.glob("*.jsonl"))
        while len(archives) > self._config.max_files:
            archives[0].unlink()
            archives.pop(0)

    def _purge_old(self) -> None:
        """Remove archived files older than auto_purge_days."""
        cutoff = datetime.now(UTC) - timedelta(days=self._config.auto_purge_days)
        for f in self._archive_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
