"""
Deterministic pipeline — fixed retrieval → single Sonnet generation.

Used when RouteDecision.pipeline == "deterministic": focused, factual queries
that don't need the agent loop. Retrieval and user context are fetched in
parallel to minimise latency.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.db.client import get_journal_entries, get_recovery_plan, get_user_profile
from app.models.orchestrator import SONNET, generate
from app.pipelines._types import PipelineResult
from app.retrieval.context_assembler import assemble
from app.retrieval.reranker import rerank
from app.retrieval.retriever import retrieve_chunks
from app.retrieval.rewriter import rewrite
from app.retrieval.router import RouteDecision


async def _fetch_user_context(user_id: str) -> dict[str, Any]:
    profile, journal, recovery = await asyncio.gather(
        get_user_profile(user_id),
        get_journal_entries(user_id, limit=5),
        get_recovery_plan(user_id),
    )
    return {"profile": profile, "journal_entries": journal, "recovery_plan": recovery}


async def run(
    query: str,
    user_id: str,
    conversation_history: list[dict[str, Any]],
    route: RouteDecision,
    top_k_retrieve: int = 20,
    top_k_rerank: int = 8,
) -> PipelineResult:
    """
    Run the deterministic pipeline.

    conversation_history: prior turns as Anthropic message dicts
                          [{"role": "user"|"assistant", "content": "..."}]
    route: RouteDecision already produced by router.route()
    """
    t_start = time.monotonic()

    # 1. Rewrite query + fetch user context in parallel
    clean_query, user_context = await asyncio.gather(
        rewrite(query, router_hint=route.rewrite, procedure_tags=route.procedure_tags),
        _fetch_user_context(user_id),
    )

    # 2. Retrieve + rerank
    chunks = await retrieve_chunks(
        query=clean_query,
        procedure_tags=route.procedure_tags or None,
        sections=route.sections or None,
        source_type=route.source_type,
        top_k=top_k_retrieve,
    )
    # When section-filtered retrieval is sparse, broaden to all sections so
    # procedure content about the query topic isn't silently excluded.
    if len(chunks) < 3 and route.sections:
        chunks = await retrieve_chunks(
            query=clean_query,
            procedure_tags=route.procedure_tags or None,
            sections=None,
            source_type=route.source_type,
            top_k=top_k_retrieve,
        )
    ranked = await rerank(clean_query, chunks, top_k=top_k_rerank)

    # 3. Assemble context
    ctx = assemble(ranked, user_context)

    # 4. Generate — single Sonnet call, no tools
    messages = list(conversation_history) + [{"role": "user", "content": query}]
    llm = await generate(messages=messages, system=ctx.system_prompt, model=SONNET)

    latency_ms = int((time.monotonic() - t_start) * 1000)

    mean_score = (
        round(sum(c.similarity for c in ranked) / len(ranked), 4) if ranked else None
    )

    return PipelineResult(
        response=llm.text or "",
        route=route,
        pipeline_mode="deterministic",
        chunk_ids=ctx.chunk_ids,
        source_names=ctx.source_names,
        mean_retrieval_score=mean_score,
        tools_called=[],
        model_generation=llm.model,
        chunk_contents=[c.content for c in ranked],
        input_tokens=llm.input_tokens,
        output_tokens=llm.output_tokens,
        cost_usd=llm.cost_usd,
        latency_ms=latency_ms,
    )
