"""
Faithfulness tests — Haiku judges whether each response is grounded in
the retrieved chunks rather than hallucinated.

Pass criteria:
  - Mean faithfulness score across all in-scope queries >= 0.70
  - No individual query scores below 0.40 (catastrophic hallucination check)
"""

from __future__ import annotations

from typing import Any

import pytest

from app.eval.scorer import score_faithfulness
from app.pipelines import deterministic as det
from app.retrieval.router import route

FAKE_USER_ID = "00000000-0000-0000-0000-000000000001"
MIN_MEAN_FAITHFULNESS = 0.70
MIN_INDIVIDUAL_FAITHFULNESS = 0.40


@pytest.mark.asyncio
async def test_mean_faithfulness_above_threshold(in_scope_cases: list[dict[str, Any]]) -> None:
    assert in_scope_cases
    scores: list[float] = []
    low_scorers: list[str] = []

    for case in in_scope_cases:
        decision = await route(case["query"])
        result = await det.run(
            query=case["query"],
            user_id=FAKE_USER_ID,
            conversation_history=[],
            route=decision,
        )
        if not result.chunk_contents or not result.response:
            continue

        faith = await score_faithfulness(case["query"], result.response, result.chunk_contents)
        if faith is None:
            continue

        scores.append(faith)
        if faith < MIN_INDIVIDUAL_FAITHFULNESS:
            low_scorers.append(
                f"{case['id']}: faithfulness={faith:.2f} — '{case['query'][:60]}'"
            )

    assert not low_scorers, (
        "Catastrophic faithfulness failures (score < 0.40):\n" + "\n".join(low_scorers)
    )

    assert scores, "No faithfulness scores collected"
    mean = sum(scores) / len(scores)
    assert mean >= MIN_MEAN_FAITHFULNESS, (
        f"Mean faithfulness {mean:.3f} below threshold {MIN_MEAN_FAITHFULNESS} "
        f"(n={len(scores)})"
    )
