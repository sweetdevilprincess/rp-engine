"""Tests for VectorSearch service and text utilities."""

from __future__ import annotations

import hashlib
import struct

import numpy as np
import pytest

from rp_engine.config import SearchConfig
from rp_engine.services.vector_search import VectorSearch, _blob_to_vec, _vec_to_blob
from rp_engine.utils.text import chunk_text, sanitize_fts_query


# ---------------------------------------------------------------------------
# Text utility tests
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("Hello world", chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_splits_at_paragraph(self):
        text = "A" * 500 + "\n\n" + "B" * 500
        chunks = chunk_text(text, chunk_size=600, overlap=50)
        assert len(chunks) >= 2

    def test_overlap(self):
        text = " ".join(["word"] * 200)
        chunks = chunk_text(text, chunk_size=100, overlap=30)
        # Verify overlap: end of chunk N should overlap with start of chunk N+1
        assert len(chunks) > 1

    def test_no_empty_chunks(self):
        text = "Some text\n\n\n\nMore text\n\n\n\nEven more"
        chunks = chunk_text(text, chunk_size=20, overlap=5)
        for chunk in chunks:
            assert chunk.strip() != ""


class TestSanitizeFtsQuery:
    def test_basic_words(self):
        result = sanitize_fts_query("hello world")
        assert '"hello"' in result
        assert '"world"' in result
        assert " OR " in result

    def test_strips_operators(self):
        result = sanitize_fts_query('hello* "world" (test)')
        assert "*" not in result
        assert "(" not in result

    def test_empty_string(self):
        assert sanitize_fts_query("") == ""

    def test_all_operators(self):
        assert sanitize_fts_query("*()^~") == ""

    def test_single_char_filtered(self):
        result = sanitize_fts_query("I a am ok")
        assert '"am"' in result
        assert '"ok"' in result

    def test_unicode_preserved(self):
        result = sanitize_fts_query("caf\u00e9 r\u00e9sum\u00e9")
        assert '"caf\u00e9"' in result


# ---------------------------------------------------------------------------
# Blob round-trip tests
# ---------------------------------------------------------------------------


class TestBlobRoundTrip:
    def test_list_to_blob_and_back(self):
        original = [1.0, 2.0, 3.0, 4.0]
        blob = _vec_to_blob(original)
        result = _blob_to_vec(blob)
        np.testing.assert_array_almost_equal(result, original)

    def test_numpy_to_blob_and_back(self):
        original = np.array([0.5, -0.3, 0.8], dtype=np.float32)
        blob = _vec_to_blob(original)
        result = _blob_to_vec(blob)
        np.testing.assert_array_almost_equal(result, original)

    def test_blob_format_is_float32(self):
        vec = [1.0, 2.0]
        blob = _vec_to_blob(vec)
        assert len(blob) == 8  # 2 * 4 bytes per float32


# ---------------------------------------------------------------------------
# Mock embed function for tests
# ---------------------------------------------------------------------------


def _mock_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic mock: hash text to seed random vector."""
    results = []
    for text in texts:
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = np.random.RandomState(seed)
        vec = rng.randn(384).astype(np.float32).tolist()
        results.append(vec)
    return results


async def mock_embed_async(texts: list[str]) -> list[list[float]]:
    return _mock_embed(texts)


# ---------------------------------------------------------------------------
# VectorSearch tests
# ---------------------------------------------------------------------------


@pytest.fixture
def search_config():
    return SearchConfig(
        vector_weight=0.7,
        bm25_weight=0.3,
        similarity_threshold=0.0,  # Low threshold for tests
        chunk_size=200,
        chunk_overlap=50,
    )


@pytest.fixture
def vector_search(db, search_config):
    return VectorSearch(db, search_config, embed_fn=mock_embed_async)


class TestIndexDocument:
    @pytest.mark.asyncio
    async def test_index_and_count(self, vector_search):
        count = await vector_search.index_document(
            "This is some test content about Dante and the mafia.",
            "test.md",
            "TestRP",
            "character",
        )
        assert count > 0

    @pytest.mark.asyncio
    async def test_reindex_replaces(self, vector_search):
        await vector_search.index_document("First version", "test.md", "TestRP")
        await vector_search.index_document("Second version", "test.md", "TestRP")

        # Should only have chunks from second version
        count = await vector_search.db.fetch_val(
            "SELECT COUNT(*) FROM vectors WHERE file_path = ?", ["test.md"]
        )
        assert count == 1  # "Second version" is short enough for 1 chunk


class TestRemoveDocument:
    @pytest.mark.asyncio
    async def test_remove(self, vector_search):
        await vector_search.index_document("Content", "test.md", "TestRP")
        removed = await vector_search.remove_document("test.md")
        assert removed > 0

        count = await vector_search.db.fetch_val(
            "SELECT COUNT(*) FROM vectors WHERE file_path = ?", ["test.md"]
        )
        assert count == 0


class TestSearch:
    @pytest.mark.asyncio
    async def test_bm25_search(self, vector_search):
        await vector_search.index_document(
            "Dante Moretti is the head of the Moretti crime family.",
            "dante.md",
            "TestRP",
        )
        await vector_search.index_document(
            "The warehouse was dark and empty.",
            "warehouse.md",
            "TestRP",
        )

        results = await vector_search.search("Moretti crime", rp_folder="TestRP")
        assert len(results) > 0
        # "Moretti crime" should match dante.md better
        assert results[0].file_path == "dante.md"

    @pytest.mark.asyncio
    async def test_vector_search(self, vector_search):
        await vector_search.index_document(
            "The penthouse was luxurious with marble floors.",
            "penthouse.md",
            "TestRP",
        )

        results = await vector_search.search(
            "luxury apartment marble",
            rp_folder="TestRP",
        )
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_empty_search(self, vector_search):
        results = await vector_search.search("anything", rp_folder="TestRP")
        assert results == []


class TestRRFFusion:
    def test_basic_fusion(self, vector_search):
        vec_results = [(1, 0.9), (2, 0.7), (3, 0.5)]
        bm25_results = [(2, 0.8), (4, 0.6), (1, 0.4)]

        fused = vector_search._rrf_fuse(vec_results, bm25_results)

        # Items appearing in both should rank higher
        ids = [r[0] for r in fused]
        # ID 2 appears in both, should be near top
        assert 2 in ids[:2]
        # ID 1 appears in both
        assert 1 in ids[:3]

    def test_empty_inputs(self, vector_search):
        assert vector_search._rrf_fuse([], []) == []
