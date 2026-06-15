"""
Scope gate tests — the fastest eval (router only, no retrieval or generation).

Pass criteria:
  - All 5 OT-* queries are blocked (in_scope=False)
  - All 25 in-scope queries are NOT blocked
"""

from __future__ import annotations

from typing import Any

import pytest

from app.retrieval.router import route


@pytest.mark.asyncio
async def test_out_of_scope_queries_are_blocked(scope_gate_cases: list[dict[str, Any]]) -> None:
    assert scope_gate_cases, "No scope gate cases in golden dataset"
    failures: list[str] = []
    for case in scope_gate_cases:
        decision = await route(case["query"])
        if decision.in_scope:
            failures.append(f"{case['id']}: expected blocked, got in_scope=True — '{case['query'][:60]}'")

    assert not failures, "Scope gate failures:\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_in_scope_queries_are_not_blocked(in_scope_cases: list[dict[str, Any]]) -> None:
    assert in_scope_cases, "No in-scope cases in golden dataset"
    failures: list[str] = []
    for case in in_scope_cases:
        decision = await route(case["query"])
        if not decision.in_scope:
            failures.append(f"{case['id']}: expected in_scope, got blocked — '{case['query'][:60]}'")

    assert not failures, "False-positive blocks:\n" + "\n".join(failures)
