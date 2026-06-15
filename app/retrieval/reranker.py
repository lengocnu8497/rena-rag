"""
Reranker — one Haiku call scores all retrieved chunks against the query.

rerank(query, chunks, top_k) → list[ChunkResult]

Chunks are presented to Haiku with truncated content; Haiku returns a JSON
array of {id, score} pairs. On any parse failure the original cosine
similarity order is preserved.
"""

from __future__ import annotations

import json
import re

from app.models.orchestrator import HAIKU, classify
from app.retrieval.retriever import ChunkResult

_CONTENT_PREVIEW = 280   # chars of chunk content shown to Haiku
_MAX_CHUNKS = 20         # hard cap to keep prompt size bounded


def _build_prompt(query: str, chunks: list[ChunkResult]) -> str:
    lines = [
        f'Query: "{query}"\n',
        "Score each chunk for relevance to the query.",
        "0.0 = irrelevant  |  0.5 = somewhat relevant  |  1.0 = directly answers the query",
        'Return ONLY a JSON array: [{"id": "<id>", "score": <0.0-1.0>}, ...]\n',
        "Chunks:",
    ]
    for i, c in enumerate(chunks, 1):
        preview = c.content[:_CONTENT_PREVIEW].replace("\n", " ")
        lines.append(
            f'[{i}] id={c.id}\n'
            f'     source={c.source_name} | section={c.section or "—"}\n'
            f'     "{preview}{"…" if len(c.content) > _CONTENT_PREVIEW else ""}"'
        )
    return "\n".join(lines)


def _parse_scores(text: str) -> dict[str, float]:
    """Extract {id: score} from Haiku's JSON array response."""
    text = text.strip()
    # strip markdown fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()

    for attempt in [text, re.search(r"\[.*\]", text, re.DOTALL)]:
        raw = attempt if isinstance(attempt, str) else (attempt.group() if attempt else None)
        if not raw:
            continue
        try:
            items = json.loads(raw)
            return {
                item["id"]: float(item["score"])
                for item in items
                if "id" in item and "score" in item
            }
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return {}


async def rerank(
    query: str,
    chunks: list[ChunkResult],
    top_k: int = 10,
) -> list[ChunkResult]:
    """
    Rerank chunks by cross-attention relevance to query.

    Returns up to top_k chunks sorted by reranker score descending.
    Falls back to original cosine similarity order on parse failure.
    """
    if not chunks:
        return []

    candidates = chunks[:_MAX_CHUNKS]

    raw = await classify(
        prompt=_build_prompt(query, candidates),
        model=HAIKU,
        max_tokens=512,
    )

    scores = _parse_scores(raw)

    if not scores:
        # fallback: original similarity order, just truncate to top_k
        return chunks[:top_k]

    def _score(c: ChunkResult) -> float:
        # blend: 80% reranker, 20% cosine similarity (keeps high-similarity
        # chunks from dropping too far if Haiku missed them)
        return scores.get(c.id, 0.0) * 0.8 + c.similarity * 0.2

    ranked = sorted(candidates, key=_score, reverse=True)
    return ranked[:top_k]
