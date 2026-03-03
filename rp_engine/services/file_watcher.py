"""Filesystem monitor for story card changes.

Uses watchfiles to watch Story Cards/**/*.md and RP State/Story_Guidelines.md.
Debounces 500ms to handle Obsidian's atomic save (write temp + rename).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from rp_engine.services.card_indexer import CardIndexer

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watches story card files and triggers reindexing on changes."""

    def __init__(
        self,
        card_indexer: CardIndexer,
        vault_root: Path,
        rp_folders: list[str],
        debounce_ms: int = 500,
    ) -> None:
        self.card_indexer = card_indexer
        self.vault_root = vault_root
        self.rp_folders = rp_folders
        self.debounce_ms = debounce_ms
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the file watcher as a background task."""
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("File watcher started for %d RP folders", len(self.rp_folders))

    async def stop(self) -> None:
        """Stop the file watcher."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("File watcher stopped")

    def _get_watch_paths(self) -> list[Path]:
        """Get all directories to watch."""
        paths = []
        for folder in self.rp_folders:
            story_cards = self.vault_root / folder / "Story Cards"
            if story_cards.is_dir():
                paths.append(story_cards)
            rp_state = self.vault_root / folder / "RP State"
            if rp_state.is_dir():
                paths.append(rp_state)
        return paths

    def _find_rp_folder(self, file_path: Path) -> str | None:
        """Determine which RP folder a file belongs to."""
        try:
            rel = file_path.relative_to(self.vault_root)
        except ValueError:
            return None
        parts = rel.parts
        if parts and parts[0] in self.rp_folders:
            return parts[0]
        return None

    async def _watch_loop(self) -> None:
        """Main watch loop using watchfiles."""
        import watchfiles

        watch_paths = self._get_watch_paths()
        if not watch_paths:
            logger.warning("No directories to watch")
            return

        logger.info("Watching paths: %s", [str(p) for p in watch_paths])

        try:
            async for changes in watchfiles.awatch(
                *watch_paths,
                debounce=self.debounce_ms,
                step=100,
                stop_event=asyncio.Event() if not self._running else None,
            ):
                if not self._running:
                    break

                for change_type, path_str in changes:
                    file_path = Path(path_str)

                    # Only process .md files
                    if file_path.suffix != ".md":
                        continue

                    rp_folder = self._find_rp_folder(file_path)
                    if not rp_folder:
                        continue

                    try:
                        if change_type in (
                            watchfiles.Change.added,
                            watchfiles.Change.modified,
                        ):
                            await self.card_indexer.index_file(rp_folder, file_path)
                            logger.debug("Reindexed: %s", file_path)
                        elif change_type == watchfiles.Change.deleted:
                            await self.card_indexer.remove_file(rp_folder, file_path)
                            logger.debug("Removed: %s", file_path)
                    except Exception:
                        logger.exception("Error processing file change: %s", file_path)

        except asyncio.CancelledError:
            logger.debug("File watcher cancelled")
        except Exception:
            logger.exception("File watcher error")
