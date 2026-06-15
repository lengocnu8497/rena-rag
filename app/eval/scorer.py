"""
Eval scorer — Haiku-based faithfulness and relevance scoring.

Both scores are written to rag_eval_logs after every /chat response.
Runs as a FastAPI BackgroundTask so it never blocks the client.

evaluate_and_log() replaces the raw _write_eval_log helper in chat.py.
"""

from __future__ import annotations

import logging
import re

from app.db.client import insert_eval_log
from app.models.orchestrator import HAIKU, classify
from app.pipelines._types import PipelineResult

logger = logging.getLogger("rena.eval")

_CHUNK_PREVIEW = 600   # match context_assembler.CHUNK_PREVIEW so scorer sees what Sonnet saw
_MAX_EVAL_CHUNKS = 8   # match context_assembler.MAX_CHUNKS


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _faithfulness_prompt(query: str, response: str, chunks: list[str]) -> str:
    context = "\n\n".join(
        f"[{i+1}] {c[:_CHUNK_PREVIEW]}{'…' if len(c) > _CHUNK_PREVIEW else ''}"
        for i, c in enumerate(chunks[:_MAX_EVAL_CHUNKS])
    )
    return (
        f"Context:\n{context}\n\n"
        f"Query: {query}\n"
        f"Response: {response}\n\n"
        "Score the response for FAITHFULNESS to the context (0.0–1.0).\n"
        "1.0 = every claim is grounded in the context above.\n"
        "0.0 = response contradicts or ignores the context.\n"
        "Return ONLY a decimal number, nothing else."
    )


def _relevance_prompt(query: str, response: str) -> str:
    return (
        f"Query: {query}\n"
        f"Response: {response}\n\n"
        "Score the response for RELEVANCE to the query (0.0–1.0).\n"
        "1.0 = response directly and completely answers the query.\n"
        "0.0 = response does not address the query at all.\n"
        "Return ONLY a decimal number, nothing else."
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_score(text: str) -> float | None:
    text = text.strip()
    m = re.search(r"\b([01](?:\.\d+)?|\.\d+)\b", text)
    if m:
        val = float(m.group(1))
        return round(max(0.0, min(1.0, val)), 3)
    return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

async def score_faithfulness(
    query: str, response: str, chunks: list[str]
) -> float | None:
    try:
        raw = await classify(
            prompt=_faithfulness_prompt(query, response, chunks),
            model=HAIKU,
            max_tokens=16,
        )
        return _parse_score(raw)
    except Exception as exc:
        logger.warning("faithfulness scoring failed: %s", exc)
        return None


async def score_relevance(query: str, response: str) -> float | None:
    try:
        raw = await classify(
            prompt=_relevance_prompt(query, response),
            model=HAIKU,
            max_tokens=16,
        )
        return _parse_score(raw)
    except Exception as exc:
        logger.warning("relevance scoring failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Combined background task
# ---------------------------------------------------------------------------

async def evaluate_and_log(
    user_id: str,
    query: str,
    result: PipelineResult,
    scope_blocked: bool = False,
    conversation_id: str | None = None,
) -> None:
    """
    Score the response with Haiku then write a single rag_eval_logs row.
    Designed to run as a FastAPI BackgroundTask — never raises.
    """
    faithfulness: float | None = None
    relevance: float | None = None

    if not scope_blocked and result.response:
        relevance = await score_relevance(query, result.response)
        if result.chunk_contents:
            faithfulness = await score_faithfulness(
                query, result.response, result.chunk_contents
            )

    try:
        await insert_eval_log(
            {
                "user_id": user_id,
                "query": query,
                "intent": result.route.intent,
                "pipeline_mode": result.pipeline_mode,
                "retrieved_chunk_ids": result.chunk_ids or None,
                "retrieved_sources": result.source_names or None,
                "mean_retrieval_score": result.mean_retrieval_score,
                "response": result.response,
                "faithfulness_score": faithfulness,
                "relevance_score": relevance,
                "tools_called": result.tools_called or None,
                "model_generation": result.model_generation,
                "model_routing": result.model_routing,
                "tokens_input": result.input_tokens,
                "tokens_output": result.output_tokens,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
                "scope_blocked": scope_blocked,
                "metadata": (
                    {"conversation_id": conversation_id} if conversation_id else {}
                ),
            }
        )
    except Exception as exc:
        logger.warning("eval log write failed: %s", exc)
