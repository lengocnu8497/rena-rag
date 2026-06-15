"""
Query router — uses Haiku to classify intent and decide pipeline mode.

route(query) → RouteDecision

  pipeline="deterministic"  focused, factual queries answered by direct retrieval
  pipeline="agent"          personalized or multi-step queries that need tool calls

The RouteDecision is passed downstream to the pipeline selector (Step 14/15)
and its fields seed the retriever's metadata pre-filters.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.models.orchestrator import HAIKU, classify

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

VALID_INTENTS = frozenset(
    ["procedure_info", "recovery_question", "consult_prep", "general_advice", "out_of_scope"]
)

VALID_SECTIONS = frozenset(
    [
        "description",
        "editorial_summary",
        "who_its_for",
        "what_is_normal",
        "what_to_watch_for",
        "recovery_overview",
        "consult_questions",
    ]
)


@dataclass
class RouteDecision:
    in_scope: bool
    pipeline: str                       # "deterministic" | "agent"
    intent: str                         # one of VALID_INTENTS
    procedure_tags: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    source_type: str | None = None      # "procedure" | "medical_paper" | "guide" | "faq"
    rewrite: str | None = None          # cleaner retrieval query if original is ambiguous


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a query router for Rena, an AI assistant specialising in aesthetic \
procedure research and post-procedure recovery. Your job is to classify the \
user query and return routing metadata.

Respond with ONLY a JSON object — no markdown fences, no explanation:

{
  "in_scope": true,
  "pipeline": "deterministic",
  "intent": "recovery_question",
  "procedure_tags": ["botox / dysport"],
  "sections": ["what_is_normal", "what_to_watch_for"],
  "source_type": null,
  "rewrite": null
}

Field rules:
- in_scope: true if the query is about aesthetic procedures, recovery, skincare, \
or consult preparation; false otherwise.
- pipeline: "deterministic" for focused, factual, lookup-style questions; \
"agent" for queries that require the user's personal context (profile, journal, \
recovery plan) or multi-step reasoning.
- intent: one of procedure_info | recovery_question | consult_prep | \
general_advice | out_of_scope
- procedure_tags: use the EXACT lowercase procedure names below — spaces not \
underscores, full names not abbreviations. Only include procedures explicitly \
mentioned or strongly implied. Empty array if none.
  Valid names: rhinoplasty, facelift, blepharoplasty, brow lift, neck lift, \
chin augmentation, otoplasty, breast augmentation, breast lift, breast reduction, \
brazilian butt lift, mommy makeover, microneedling, chemical peel, \
laser resurfacing, ipl photofacial, hydrafacial, ultherapy / hifu, \
rf microneedling, laser hair removal, botox / dysport, lip filler, cheek filler, \
jawline filler, under eye filler, dermal filler, kybella, sculptra, \
prp / prf therapy, coolsculpting, emsculpt / emsculpt neo, rf skin tightening, \
pdo thread lift, microfocused ultrasound, liposuction, tummy tuck, fat transfer, \
body contouring surgery
- sections: subset of [description, editorial_summary, who_its_for, \
what_is_normal, what_to_watch_for, recovery_overview, consult_questions] \
most likely to contain the answer. Empty array means search all sections.
- source_type: "procedure" | "medical_paper" | "guide" | "faq" | null
- rewrite: a cleaner, more specific retrieval query if the original is vague or \
conversational; null if the original is already precise.\
"""


# ---------------------------------------------------------------------------
# JSON extraction — tolerates markdown fences and surrounding text
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> dict:
    text = text.strip()
    for attempt in [
        text,
        re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip(),
    ]:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass
    # last resort: grab first {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Safe defaults — used when Haiku returns unparseable output
# ---------------------------------------------------------------------------

def _safe_decision(query: str) -> RouteDecision:
    return RouteDecision(in_scope=True, pipeline="agent", intent="general_advice")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def route(query: str) -> RouteDecision:
    """
    Classify a user query and return a RouteDecision.
    Falls back to agent/general_advice on any parsing failure.
    """
    raw = await classify(
        prompt=f"{_SYSTEM}\n\nUser query: {query}",
        model=HAIKU,
        max_tokens=300,
    )

    data = _parse_json(raw)
    if not data:
        return _safe_decision(query)

    in_scope: bool = bool(data.get("in_scope", True))
    pipeline: str = data.get("pipeline", "agent")
    if pipeline not in ("deterministic", "agent"):
        pipeline = "agent"

    intent: str = data.get("intent", "general_advice")
    if intent not in VALID_INTENTS:
        intent = "general_advice"

    procedure_tags: list[str] = [
        t.lower().replace("_", " ") for t in data.get("procedure_tags", []) if isinstance(t, str)
    ]

    sections: list[str] = [
        s for s in data.get("sections", []) if s in VALID_SECTIONS
    ]

    source_type: str | None = data.get("source_type")
    if source_type not in ("procedure", "medical_paper", "guide", "faq", None):
        source_type = None

    rewrite: str | None = data.get("rewrite") or None

    return RouteDecision(
        in_scope=in_scope,
        pipeline=pipeline,
        intent=intent,
        procedure_tags=procedure_tags,
        sections=sections,
        source_type=source_type,
        rewrite=rewrite,
    )
