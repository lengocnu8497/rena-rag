"""
Query rewriter — converts conversational queries into retrieval-optimised form.

Haiku strips filler language, expands abbreviations, and produces a
noun-dense phrase that scores better against procedure/section embeddings.

Falls back to the router hint (if any) or the original query on failure.
"""

from __future__ import annotations

from app.models.orchestrator import HAIKU, classify

_PROMPT = """\
You are a search query optimiser for a medical aesthetics knowledge base.
Rewrite the user query into a concise, noun-dense retrieval query.

Rules:
- Remove conversational filler ("I was wondering", "can you tell me", etc.)
- Expand abbreviations (BBL → Brazilian butt lift, RF → radiofrequency, etc.)
- Include relevant clinical/aesthetic terminology the source text likely uses
- Keep it to one or two lines — do NOT add explanation
- Output ONLY the rewritten query, nothing else

Examples:
  "omg my face is so puffy after my botox yesterday is that normal??"
  → "botox day 1 swelling facial puffiness normal recovery"

  "how do i know if my nose job is healing right"
  → "rhinoplasty healing indicators normal recovery signs week by week"

  "what questions should i bring up when i meet my surgeon for fillers"
  → "dermal filler consultation questions surgeon preparation"

User query: {query}\
"""


async def rewrite(
    query: str,
    router_hint: str | None = None,
    procedure_tags: list[str] | None = None,
) -> str:
    """
    Return a retrieval-optimised version of the query.

    router_hint: the rewrite field from RouteDecision (used as fallback).
    procedure_tags: if provided, appended to the prompt so Haiku knows
                    which procedures are in play.
    """
    prompt = _PROMPT.format(query=query)
    if procedure_tags:
        prompt += f"\nKnown procedures in query: {', '.join(procedure_tags)}"

    result = await classify(prompt=prompt, model=HAIKU, max_tokens=120)
    result = result.strip()

    # Reject empty or suspiciously long outputs
    if not result or len(result) > 400:
        return router_hint or query

    return result
