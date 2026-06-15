"""
Agent loop pipeline — used when RouteDecision.pipeline == "agent".

Runs a multi-turn Sonnet conversation with access to all 6 tools.
The model calls tools until it has enough context, then produces a final
end_turn response. Capped at max_iterations to prevent runaway loops.

Tool calls are executed in parallel per turn. Chunk IDs from
retrieve_knowledge tool results are captured for eval logging.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from app.models.orchestrator import SONNET, generate
from app.pipelines._types import PipelineResult
from app.retrieval.context_assembler import _BASE_SYSTEM
from app.retrieval.router import RouteDecision
from app.tools import TOOL_DEFINITIONS, dispatch

MAX_ITERATIONS = 6

# Extend the base persona with agent-specific tool guidance
_SYSTEM = (
    _BASE_SYSTEM
    + """

Tool use guidelines:
- Call get_user_context first whenever the query is personal or recovery-related.
- Call retrieve_knowledge for any clinical or procedural fact.
- Call recall_memory if the user references something from a past conversation.
- Call lookup_procedure when the user names a specific procedure and you need full details.
- Call save_memory at the end of any substantive multi-turn conversation.
- Call check_scope only when the query is ambiguous and you need to confirm it is in scope.
- Do not call a tool more than once with identical inputs in the same session."""
)


def _extract_chunk_ids(tool_results: list[dict[str, Any]]) -> list[str]:
    """Pull chunk UUIDs out of retrieve_knowledge tool_result content blocks."""
    ids: list[str] = []
    for block in tool_results:
        if block.get("type") != "tool_result":
            continue
        try:
            data = json.loads(block["content"])
            for chunk in data.get("chunks", []):
                if chunk_id := chunk.get("id"):
                    ids.append(chunk_id)
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return ids


def _extract_source_names(tool_results: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for block in tool_results:
        if block.get("type") != "tool_result":
            continue
        try:
            data = json.loads(block["content"])
            for chunk in data.get("chunks", []):
                if name := chunk.get("source_name"):
                    if name not in names:
                        names.append(name)
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return names


async def run(
    query: str,
    user_id: str,
    conversation_history: list[dict[str, Any]],
    route: RouteDecision,
    max_iterations: int = MAX_ITERATIONS,
) -> PipelineResult:
    t_start = time.monotonic()

    messages: list[dict[str, Any]] = list(conversation_history) + [
        {"role": "user", "content": query}
    ]

    total_input = 0
    total_output = 0
    total_cost = 0.0
    tools_called: list[str] = []
    chunk_ids: list[str] = []
    source_names: list[str] = []
    final_text: str | None = None
    model_used = SONNET

    for _ in range(max_iterations):
        llm = await generate(
            messages=messages,
            system=_SYSTEM,
            tools=TOOL_DEFINITIONS,
            model=SONNET,
        )

        total_input += llm.input_tokens
        total_output += llm.output_tokens
        total_cost += llm.cost_usd
        model_used = llm.model

        # Append raw assistant message for the next turn
        messages.append({"role": "assistant", "content": llm.raw_message.content})

        if llm.stop_reason == "end_turn" or not llm.tool_calls:
            final_text = llm.text
            break

        # Execute all tool calls for this turn in parallel
        results = await asyncio.gather(
            *[dispatch(tc.name, tc.input, user_id) for tc in llm.tool_calls]
        )

        # Track tool names (deduplicated, ordered by first call)
        for tc in llm.tool_calls:
            if tc.name not in tools_called:
                tools_called.append(tc.name)

        # Build tool_result blocks for the next user message
        tool_result_blocks: list[dict[str, Any]] = [
            {
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result.to_text(),
            }
            for tc, result in zip(llm.tool_calls, results)
        ]

        # Capture chunk IDs from retrieve_knowledge results
        chunk_ids.extend(_extract_chunk_ids(tool_result_blocks))
        source_names.extend(_extract_source_names(tool_result_blocks))

        messages.append({"role": "user", "content": tool_result_blocks})

    latency_ms = int((time.monotonic() - t_start) * 1000)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_source_names = [n for n in source_names if not (n in seen or seen.add(n))]  # type: ignore[func-returns-value]

    return PipelineResult(
        response=final_text or "",
        route=route,
        pipeline_mode="agent",
        chunk_ids=list(dict.fromkeys(chunk_ids)),
        source_names=unique_source_names,
        mean_retrieval_score=None,
        tools_called=tools_called,
        model_generation=model_used,
        input_tokens=total_input,
        output_tokens=total_output,
        cost_usd=total_cost,
        latency_ms=latency_ms,
    )
