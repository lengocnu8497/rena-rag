import asyncio

from app.tools._types import ToolResult

DEFINITION = {
    "name": "get_user_context",
    "description": (
        "Fetch the current user's profile, recent journal entries, and active recovery plan. "
        "Always call this before giving personalised advice about the user's specific situation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "include_journal": {
                "type": "boolean",
                "description": "Include recent journal entries (default true)",
            },
            "journal_limit": {
                "type": "integer",
                "description": "Number of journal entries to fetch (default 5, max 10)",
            },
        },
    },
}


async def run(inputs: dict, user_id: str) -> ToolResult:
    from app.db.client import get_journal_entries, get_recovery_plan, get_user_profile

    include_journal = inputs.get("include_journal", True)
    journal_limit = min(inputs.get("journal_limit", 5), 10)

    async def _journal() -> list:
        return await get_journal_entries(user_id, limit=journal_limit)

    try:
        if include_journal:
            profile, journal, recovery = await asyncio.gather(
                get_user_profile(user_id),
                _journal(),
                get_recovery_plan(user_id),
            )
        else:
            profile, recovery = await asyncio.gather(
                get_user_profile(user_id),
                get_recovery_plan(user_id),
            )
            journal = []

        return ToolResult(
            content={
                "profile": profile,
                "journal_entries": journal,
                "recovery_plan": recovery,
            }
        )
    except Exception as exc:
        return ToolResult(content={}, error=str(exc))
