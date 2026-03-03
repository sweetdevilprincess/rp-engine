"""Tests for file watcher."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from rp_engine.services.file_watcher import FileWatcher


class TestFileWatcher:
    def test_get_watch_paths(self, sample_card_dir):
        indexer = MagicMock()
        watcher = FileWatcher(indexer, sample_card_dir, ["TestRP"])
        paths = watcher._get_watch_paths()
        assert len(paths) >= 1
        assert any("Story Cards" in str(p) for p in paths)

    def test_find_rp_folder(self, sample_card_dir):
        indexer = MagicMock()
        watcher = FileWatcher(indexer, sample_card_dir, ["TestRP"])
        file_path = sample_card_dir / "TestRP" / "Story Cards" / "Characters" / "test.md"
        assert watcher._find_rp_folder(file_path) == "TestRP"

    def test_find_rp_folder_unknown(self, sample_card_dir):
        indexer = MagicMock()
        watcher = FileWatcher(indexer, sample_card_dir, ["TestRP"])
        file_path = Path("/some/other/path/test.md")
        assert watcher._find_rp_folder(file_path) is None

    def test_empty_folders(self, tmp_path):
        indexer = MagicMock()
        watcher = FileWatcher(indexer, tmp_path, [])
        paths = watcher._get_watch_paths()
        assert len(paths) == 0

    async def test_start_stop(self, sample_card_dir):
        indexer = MagicMock()
        watcher = FileWatcher(indexer, sample_card_dir, ["TestRP"])
        # Just verify start/stop don't crash (actual watching requires real files)
        watcher.start()
        assert watcher._running is True
        await watcher.stop()
        assert watcher._running is False
