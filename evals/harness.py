"""
Eval harness — standalone runner for the full golden dataset.

Usage:
  uv run python -m evals.harness                     # run all 30 cases
  uv run python -m evals.harness --fail-below 0.80   # exit 1 if mean faithfulness < 0.80
  uv run python -m evals.harness --category recovery  # filter by category
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from app.db.client import init_client  # noqa: E402
from app.eval.scorer import score_faithfulness  # noqa: E402
from app.pipelines import deterministic as det  # noqa: E402
from app.retrieval.router import route  # noqa: E402
from evals.metrics import format_table, mean, percentile  # noqa: E402

FAKE_USER_ID = "00000000-0000-0000-0000-000000000001"


async def run_case(case: dict) -> dict:
    t0 = time.monotonic()
    decision = await route(case["query"])

    if not decision.in_scope:
        return {
            "id": case["id"],
            "category": case["category"],
            "blocked": True,
            "expected_block": case["should_block"],
            "correct": case["should_block"],
            "chunks": 0,
            "retrieval_score": None,
            "faithfulness": None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "error": None,
        }

    if case["should_block"]:
        return {
            "id": case["id"],
            "category": case["category"],
            "blocked": False,
            "expected_block": True,
            "correct": False,
            "chunks": 0,
            "retrieval_score": None,
            "faithfulness": None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "error": "false negative: in-scope routing for should_block=True query",
        }

    try:
        result = await det.run(
            query=case["query"],
            user_id=FAKE_USER_ID,
            conversation_history=[],
            route=decision,
        )
    except Exception as exc:
        return {
            "id": case["id"],
            "category": case["category"],
            "blocked": False,
            "expected_block": False,
            "correct": False,
            "chunks": 0,
            "retrieval_score": None,
            "faithfulness": None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "error": str(exc),
        }

    faith: float | None = None
    if result.chunk_contents and result.response:
        faith = await score_faithfulness(case["query"], result.response, result.chunk_contents)

    return {
        "id": case["id"],
        "category": case["category"],
        "blocked": False,
        "expected_block": False,
        "correct": True,
        "chunks": len(result.chunk_ids or []),
        "retrieval_score": result.mean_retrieval_score,
        "faithfulness": faith,
        "latency_ms": result.latency_ms,
        "error": None,
    }


async def main(fail_below: float | None, category: str | None) -> int:
    await init_client()

    dataset_path = Path(__file__).parent / "golden_dataset.json"
    cases = json.loads(dataset_path.read_text())
    if category:
        cases = [c for c in cases if c["category"] == category]

    print(f"Running {len(cases)} eval cases…\n")

    results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i:2d}/{len(cases)}] {case['id']}  {case['query'][:55]}…")
        r = await run_case(case)
        results.append(r)
        status = "✓" if r["correct"] else "✗"
        faith_str = f"faith={r['faithfulness']:.2f}" if r["faithfulness"] is not None else "faith=—"
        score_str = f"sim={r['retrieval_score']:.3f}" if r["retrieval_score"] else "sim=—"
        print(f"         {status}  chunks={r['chunks']}  {score_str}  {faith_str}  {r['latency_ms']}ms")
        if r["error"]:
            print(f"         ERROR: {r['error']}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    in_scope = [r for r in results if not r["expected_block"]]
    scope_gate = [r for r in results if r["expected_block"]]

    # Scope gate accuracy
    sg_correct = sum(1 for r in scope_gate if r["correct"])
    print(f"Scope gate accuracy : {sg_correct}/{len(scope_gate)} ({sg_correct/max(len(scope_gate),1)*100:.0f}%)")

    # Retrieval
    chunk_hits = [r for r in in_scope if r["chunks"] > 0]
    print(f"Chunk retrieval     : {len(chunk_hits)}/{len(in_scope)} queries returned ≥1 chunk")

    sim_scores = [r["retrieval_score"] for r in in_scope if r["retrieval_score"] is not None]
    sim_mean = mean(sim_scores)
    print(f"Mean cosine sim     : {sim_mean:.3f}" if sim_mean else "Mean cosine sim     : —")

    # Faithfulness
    faith_scores = [r["faithfulness"] for r in in_scope if r["faithfulness"] is not None]
    faith_mean = mean(faith_scores)
    print(f"Mean faithfulness   : {faith_mean:.3f}" if faith_mean else "Mean faithfulness   : —")

    # Latency
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] is not None]
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    print(f"Latency P50 / P95   : {p50:.0f}ms / {p95:.0f}ms" if p50 and p95 else "Latency             : —")

    # Per-category breakdown
    categories = sorted({r["category"] for r in results})
    cat_rows = []
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        cat_faith = [r["faithfulness"] for r in cat_results if r["faithfulness"] is not None]
        cat_sims = [r["retrieval_score"] for r in cat_results if r["retrieval_score"] is not None]
        cat_rows.append({
            "category": cat,
            "n": len(cat_results),
            "correct": sum(1 for r in cat_results if r["correct"]),
            "mean_sim": f"{mean(cat_sims):.3f}" if cat_sims else "—",
            "mean_faith": f"{mean(cat_faith):.3f}" if cat_faith else "—",
        })

    print("\n" + format_table(cat_rows, ["category", "n", "correct", "mean_sim", "mean_faith"]))

    # Fail-below check
    if fail_below is not None and faith_mean is not None and faith_mean < fail_below:
        print(f"\n✗ FAILED: mean faithfulness {faith_mean:.3f} < --fail-below {fail_below}")
        return 1

    print("\n✓ Eval complete")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rena RAG eval harness")
    parser.add_argument("--fail-below", type=float, default=None,
                        help="Exit 1 if mean faithfulness falls below this threshold")
    parser.add_argument("--category", type=str, default=None,
                        help="Run only cases matching this category")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.fail_below, args.category)))
