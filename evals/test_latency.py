"""
Latency tests.

Pass criteria:
  - P95 end-to-end pipeline latency < 4000ms across all in-scope queries
  - No single query exceeds 10000ms (hard timeout)
"""

from __future__ import annotations

from typing import Any

import pytest

from app.pipelines import deterministic as det
from app.retrieval.router import route
from evals.metrics import percentile

FAKE_USER_ID = "00000000-0000-0000-0000-000000000001"
P95_LATENCY_LIMIT_MS = 4000
HARD_TIMEOUT_MS = 10_000


@pytest.mark.asyncio
async def test_p95_latency_under_limit(in_scope_cases: list[dict[str, Any]]) -> None:
    assert in_scope_cases
    latencies: list[float] = []
    hard_breaches: list[str] = []

    for case in in_scope_cases:
        decision = await route(case["query"])
        result = await det.run(
            query=case["query"],
            user_id=FAKE_USER_ID,
            conversation_history=[],
            route=decision,
        )
        ms = result.latency_ms
        latencies.append(ms)
        if ms > HARD_TIMEOUT_MS:
            hard_breaches.append(f"{case['id']}: {ms}ms — '{case['query'][:60]}'")

    assert not hard_breaches, (
        f"Hard timeout ({HARD_TIMEOUT_MS}ms) breached:\n" + "\n".join(hard_breaches)
    )

    p95 = percentile(latencies, 95)
    assert p95 is not None
    assert p95 <= P95_LATENCY_LIMIT_MS, (
        f"P95 latency {p95:.0f}ms exceeds {P95_LATENCY_LIMIT_MS}ms limit "
        f"(n={len(latencies)}, median={percentile(latencies, 50):.0f}ms)"
    )
