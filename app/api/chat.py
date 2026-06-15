"""
POST /chat — main entry point for the Rena RAG service.

Flow:
  1. Verify Supabase JWT → user_id
  2. Route query (Haiku) → RouteDecision
  3. Scope check — stream canned response if out of scope
  4. Select pipeline: deterministic | agent
  5. Stream SSE events: tool_call* → done → [DONE]
  6. Fire eval log (asyncio.create_task — never blocks client)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.jwt import get_current_user
from app.eval.scorer import evaluate_and_log
from app.pipelines import agent as agent_pipeline
from app.pipelines import deterministic as det_pipeline
from app.pipelines._types import PipelineResult
from app.retrieval.router import RouteDecision, route as do_route

router = APIRouter()
logger = logging.getLogger("rena.chat")

_OUT_OF_SCOPE = (
    "I'm Rena, your aesthetic procedure assistant — I'm here to help with "
    "cosmetic treatments, recovery, skincare, and consultation prep. "
    "That topic is outside what I can help with. Is there something "
    "aesthetic-related I can assist you with?"
)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class _Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    conversation_history: list[_Message] = Field(default_factory=list, max_length=50)
    conversation_id: str | None = None


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _scope_blocked_result(route: RouteDecision) -> PipelineResult:
    return PipelineResult(
        response=_OUT_OF_SCOPE,
        route=route,
        pipeline_mode="blocked",
        chunk_ids=[],
        source_names=[],
        mean_retrieval_score=None,
        tools_called=[],
        model_generation="none",
    )


# ---------------------------------------------------------------------------
# Stream generator
# ---------------------------------------------------------------------------

async def _chat_stream(
    body: ChatRequest,
    user_id: str,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    history = [{"role": m.role, "content": m.content} for m in body.conversation_history]

    # 1. Route
    route = await do_route(body.query)

    # 2. Scope gate
    if not route.in_scope:
        result = _scope_blocked_result(route)
        asyncio.create_task(
            evaluate_and_log(user_id, body.query, result, True, conversation_id)
        )
        yield _sse({
            "type": "done",
            "reply": result.response,
            "response_id": conversation_id,
            "model": "none",
            "tokens_used": 0,
            "cost_usd": 0.0,
            "reset_context": False,
        })
        yield "data: [DONE]\n\n"
        return

    # 3. Run pipeline
    try:
        if route.pipeline == "deterministic":
            result = await det_pipeline.run(
                query=body.query,
                user_id=user_id,
                conversation_history=history,
                route=route,
            )
        else:
            result = await agent_pipeline.run(
                query=body.query,
                user_id=user_id,
                conversation_history=history,
                route=route,
            )
    except Exception as exc:
        logger.exception("pipeline error: %s", exc)
        yield _sse({"type": "error", "error": "An error occurred processing your request"})
        yield "data: [DONE]\n\n"
        return

    # 4. Fire eval log (non-blocking)
    asyncio.create_task(
        evaluate_and_log(user_id, body.query, result, False, conversation_id)
    )

    # 5. Emit tool_call events (retroactive; shows agent activity in UI)
    for tool_name in result.tools_called:
        yield _sse({"type": "tool_call", "tool": tool_name, "status": "running"})
        yield _sse({"type": "tool_call", "tool": tool_name, "status": "complete"})

    # 6. Done
    yield _sse({
        "type": "done",
        "reply": result.response,
        "response_id": conversation_id,
        "model": result.model_generation,
        "tokens_used": result.input_tokens + result.output_tokens,
        "cost_usd": result.cost_usd,
        "reset_context": False,
    })
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", tags=["chat"])
async def chat(
    body: ChatRequest,
    user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    conversation_id = body.conversation_id or str(uuid.uuid4())
    return StreamingResponse(
        _chat_stream(body, user_id, conversation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
