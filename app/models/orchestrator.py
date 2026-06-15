"""
Model orchestrator — Anthropic async client with cost tracking.

Two entry points:
  generate()  — full message turn; handles text and tool_use stop reasons.
                Used by the agent loop (Step 15).
  classify()  — single-turn text completion for lightweight Haiku tasks
                (scope check, query routing, reranking, eval scoring).

LLMResponse.raw_message is the Anthropic Message object. Pass it back as
{"role": "assistant", "content": raw_message.content} in multi-turn loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from app.config import settings

# ---------------------------------------------------------------------------
# Model IDs
# ---------------------------------------------------------------------------

SONNET = "claude-sonnet-4-6"       # generation
HAIKU = "claude-haiku-4-5-20251001" # routing, reranking, eval, scope

# ---------------------------------------------------------------------------
# Pricing  (USD per 1M tokens — verify against Anthropic console)
# ---------------------------------------------------------------------------

_PRICING: dict[str, tuple[float, float]] = {
    SONNET: (3.00, 15.00),
    HAIKU:  (0.80,  4.00),
}


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = _PRICING.get(model, (3.00, 15.00))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    stop_reason: str            # "end_turn" | "tool_use" | "max_tokens"
    text: str | None            # populated when stop_reason == "end_turn"
    tool_calls: list[ToolCall]  # populated when stop_reason == "tool_use"
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw_message: Message        # pass as {"role":"assistant","content":msg.content}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate(
    messages: list[dict[str, Any]],
    system: str = "",
    tools: list[dict[str, Any]] | None = None,
    model: str = SONNET,
    max_tokens: int = 2048,
) -> LLMResponse:
    """
    Single Anthropic API call.

    For the agent loop, check stop_reason:
      "end_turn"  → response is in .text; conversation is done.
      "tool_use"  → execute .tool_calls, append results, call generate() again.
    """
    client = _get_client()

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    msg: Message = await client.messages.create(**kwargs)

    text: str | None = None
    tool_calls: list[ToolCall] = []

    for block in msg.content:
        if isinstance(block, TextBlock) and block.text:
            text = (text or "") + block.text
        elif isinstance(block, ToolUseBlock):
            tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

    return LLMResponse(
        stop_reason=msg.stop_reason or "end_turn",
        text=text,
        tool_calls=tool_calls,
        model=msg.model,
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
        cost_usd=_cost(msg.model, msg.usage.input_tokens, msg.usage.output_tokens),
        raw_message=msg,
    )


async def classify(
    prompt: str,
    model: str = HAIKU,
    max_tokens: int = 256,
) -> str:
    """
    Lightweight single-turn completion for classification tasks.
    Returns the text content directly (empty string on failure).
    """
    resp = await generate(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        max_tokens=max_tokens,
    )
    return resp.text or ""
