"""
Retrieval layer — embeds a query string and calls pgvector RPC functions.

Two entry points:
  retrieve_chunks  — knowledge_chunks ANN search with optional metadata pre-filters
  retrieve_memory  — conversation_memory ANN search scoped to a single user

Both return typed dataclasses so callers never touch raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.client import vector_search_chunks, vector_search_memory
from app.models.embedder import embed


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ChunkResult:
    id: str
    source_type: str
    source_name: str
    chunk_index: int
    section: str | None
    procedure_tags: list[str]
    paper_year: int | None
    content: str
    metadata: dict[str, Any]
    similarity: float
    evidence_grade: str | None = None


@dataclass
class MemoryResult:
    id: str
    conversation_id: str | None
    summary: str
    procedures_discussed: list[str]
    similarity: float
    created_at: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_chunks(
    query: str,
    procedure_tags: list[str] | None = None,
    sections: list[str] | None = None,
    source_type: str | None = None,
    top_k: int = 20,
    min_score: float = 0.55,
) -> list[ChunkResult]:
    """
    Embed query, run ANN search over knowledge_chunks, return scored results.

    procedure_tags / sections / source_type are passed through as pgvector
    pre-filters (evaluated on B-tree/GIN indexes before the ANN scan).
    """
    embedding = await embed(query)
    rows = await vector_search_chunks(
        embedding=embedding,
        procedure_tags=procedure_tags,
        section=sections,
        source_type=source_type,
        top_k=top_k,
        min_score=min_score,
    )
    return [ChunkResult(**row) for row in rows]


async def retrieve_memory(
    user_id: str,
    query: str,
    top_k: int = 3,
) -> list[MemoryResult]:
    """
    Embed query, run ANN search over this user's conversation_memory summaries.
    """
    embedding = await embed(query)
    rows = await vector_search_memory(
        user_id=user_id,
        embedding=embedding,
        top_k=top_k,
    )
    return [MemoryResult(**row) for row in rows]
