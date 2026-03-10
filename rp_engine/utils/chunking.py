"""Chunking configuration resolution — per-RP override > global default.

Shared by ExchangeWriter (embedding), RP router (endpoints), and any
service that needs to know which chunking strategy applies to a given RP.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChunkingParams:
    """Resolved chunking parameters for an RP."""

    strategy: str
    chunk_size: int
    chunk_overlap: int


async def get_effective_chunking(
    db, rp_folder: str, *, fallback_config=None
) -> ChunkingParams:
    """Get the effective chunking config for an RP (per-RP override > global).

    Args:
        db: Database instance with ``fetch_one()``
        rp_folder: RP folder name to look up
        fallback_config: Optional ``SearchConfig`` to use as global default.
            If None, loads ``get_config().search`` lazily.

    Returns:
        ChunkingParams with resolved strategy, chunk_size, chunk_overlap.
    """
    row = await db.fetch_one(
        "SELECT strategy, chunk_size, chunk_overlap FROM rp_chunking_config WHERE rp_folder = ?",
        [rp_folder],
    )
    if row:
        return ChunkingParams(
            strategy=row["strategy"],
            chunk_size=row["chunk_size"],
            chunk_overlap=row["chunk_overlap"],
        )

    # Fall back to global config
    if fallback_config is None:
        from rp_engine.config import get_config

        fallback_config = get_config().search

    return ChunkingParams(
        strategy=fallback_config.chunking_strategy,
        chunk_size=fallback_config.chunk_size,
        chunk_overlap=fallback_config.chunk_overlap,
    )
