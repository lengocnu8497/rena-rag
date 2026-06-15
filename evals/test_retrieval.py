"""
Retrieval quality tests.

Pass criteria:
  - Every in-scope query retrieves at least 1 chunk
  - Mean cosine similarity across all retrieved top chunks >= 0.55
"""

from __future__ import annotations

from typing import Any

import pytest

from app.pipelines import deterministic as det
from app.retrieval.router import route

FAKE_USER_ID = "00000000-0000-0000-0000-000000000001"
MIN_MEAN_SIMILARITY = 0.55


@pytest.mark.asyncio
async def test_every_in_scope_query_retrieves_chunks(in_scope_cases: list[dict[str, Any]]) -> None:
    assert in_scope_cases
    failures: list[str] = []
    for case in in_scope_cases:
        decision = await route(case["query"])
        result = await det.run(
            query=case["query"],
            user_id=FAKE_USER_ID,
            conversation_history=[],
            route=decision,
        )
        if not result.chunk_ids:
            failures.append(
                f"{case['id']} ({case['procedure']}): 0 chunks retrieved"
            )

    assert not failures, "Retrieval misses:\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_mean_retrieval_score_above_threshold(in_scope_cases: list[dict[str, Any]]) -> None:
    assert in_scope_cases
    scores: list[float] = []
    for case in in_scope_cases:
        decision = await route(case["query"])
        result = await det.run(
            query=case["query"],
            user_id=FAKE_USER_ID,
            conversation_history=[],
            route=decision,
        )
        if result.mean_retrieval_score is not None:
            scores.append(result.mean_retrieval_score)

    assert scores, "No retrieval scores collected"
    mean = sum(scores) / len(scores)
    assert mean >= MIN_MEAN_SIMILARITY, (
        f"Mean retrieval score {mean:.3f} below threshold {MIN_MEAN_SIMILARITY} "
        f"(n={len(scores)})"
    )
