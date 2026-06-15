"""
POST /api/inspect — run the full retrieval pipeline and return all intermediate
results for the dashboard's Retrieval Inspector page.

No auth: internal engineering tool only.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.orchestrator import SONNET, generate
from app.retrieval.context_assembler import assemble
from app.retrieval.reranker import rerank
from app.retrieval.retriever import ChunkResult, retrieve_chunks
from app.retrieval.rewriter import rewrite
from app.retrieval.router import route as do_route

router = APIRouter(prefix="/api", tags=["internal"])


class InspectRequest(BaseModel):
    query: str


class ChunkItem(BaseModel):
    id: str
    source_name: str
    section: str | None
    procedure_tags: list[str]
    content: str
    similarity: float


class RouteInfo(BaseModel):
    in_scope: bool
    pipeline: str
    intent: str
    procedure_tags: list[str]
    sections: list[str]
    source_type: str | None
    rewrite: str | None


class InspectResponse(BaseModel):
    query: str
    rewritten_query: str
    route: RouteInfo
    retrieved_chunks: list[ChunkItem]
    reranked_chunks: list[ChunkItem]
    response: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def _to_item(c: ChunkResult) -> ChunkItem:
    return ChunkItem(
        id=c.id,
        source_name=c.source_name,
        section=c.section,
        procedure_tags=c.procedure_tags,
        content=c.content,
        similarity=c.similarity,
    )


@router.post("/inspect", response_model=InspectResponse)
async def inspect(req: InspectRequest) -> InspectResponse:
    t_start = time.monotonic()

    route_decision = await do_route(req.query)

    rewritten = await rewrite(
        req.query,
        router_hint=route_decision.rewrite,
        procedure_tags=route_decision.procedure_tags,
    )

    chunks = await retrieve_chunks(
        query=rewritten,
        procedure_tags=route_decision.procedure_tags or None,
        sections=route_decision.sections or None,
        source_type=route_decision.source_type,
        top_k=20,
    )

    ranked = await rerank(rewritten, chunks, top_k=8)

    ctx = assemble(ranked)
    llm = await generate(
        messages=[{"role": "user", "content": req.query}],
        system=ctx.system_prompt,
        model=SONNET,
    )

    latency_ms = int((time.monotonic() - t_start) * 1000)

    return InspectResponse(
        query=req.query,
        rewritten_query=rewritten,
        route=RouteInfo(
            in_scope=route_decision.in_scope,
            pipeline=route_decision.pipeline,
            intent=route_decision.intent,
            procedure_tags=route_decision.procedure_tags,
            sections=route_decision.sections,
            source_type=route_decision.source_type,
            rewrite=route_decision.rewrite,
        ),
        retrieved_chunks=[_to_item(c) for c in chunks],
        reranked_chunks=[_to_item(c) for c in ranked],
        response=llm.text or "",
        input_tokens=llm.input_tokens,
        output_tokens=llm.output_tokens,
        cost_usd=llm.cost_usd,
        latency_ms=latency_ms,
    )
