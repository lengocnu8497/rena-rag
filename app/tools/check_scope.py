"""
Scope enforcement — heuristic implementation.
Step 9 (orchestrator) upgrades the internal logic to a Haiku classifier,
but the tool interface and ToolResult contract stay identical.
"""

from app.tools._types import ToolResult

DEFINITION = {
    "name": "check_scope",
    "description": (
        "Determine whether a user query is within Rena's scope: aesthetic procedures, "
        "cosmetic surgery, recovery, skincare, and related topics. "
        "Call before answering if the query seems unrelated to aesthetics."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The user's query to classify",
            },
        },
        "required": ["query"],
    },
}

_IN_SCOPE: frozenset[str] = frozenset(
    [
        "botox", "filler", "rhinoplasty", "facelift", "blepharoplasty",
        "liposuction", "tummy tuck", "abdominoplasty", "breast", "augmentation",
        "reduction", "lift", "implant", "microneedling", "laser", "peel",
        "chemical peel", "hydrafacial", "ultherapy", "coolsculpting", "kybella",
        "prp", "rf", "radiofrequency", "sculptra", "juvederm", "restylane",
        "dysport", "xeomin", "recovery", "swelling", "bruising", "downtime",
        "aftercare", "scar", "healing", "procedure", "surgery", "cosmetic",
        "aesthetic", "skin", "wrinkle", "anti-aging", "anti aging", "collagen",
        "hyaluronic", "injection", "treatment", "consultation", "surgeon",
        "dermatologist", "med spa", "clinic",
    ]
)

_OUT_OF_SCOPE_SIGNALS: frozenset[str] = frozenset(
    [
        "stock", "invest", "crypto", "weather", "sport", "recipe", "cook",
        "travel", "flight", "hotel", "politics", "news", "election", "tax",
        "legal advice", "lawyer", "divorce", "code", "programming",
    ]
)


async def run(inputs: dict, user_id: str) -> ToolResult:
    query = inputs["query"].lower()

    out_of_scope = any(sig in query for sig in _OUT_OF_SCOPE_SIGNALS)
    in_scope = any(kw in query for kw in _IN_SCOPE)

    if out_of_scope and not in_scope:
        return ToolResult(
            content={
                "in_scope": False,
                "reason": "Query does not appear to relate to aesthetic procedures or recovery.",
            }
        )

    return ToolResult(
        content={
            "in_scope": True,
            "reason": "Query relates to aesthetic procedures or recovery.",
        }
    )
