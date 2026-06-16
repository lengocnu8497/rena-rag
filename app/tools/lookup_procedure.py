from app.tools._types import ToolResult

DEFINITION = {
    "name": "lookup_procedure",
    "description": (
        "Look up the full details for a specific aesthetic procedure by name. "
        "More precise than retrieve_knowledge when the user names an exact procedure. "
        "Returns the procedure's overview, recovery, risks, and consult questions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Procedure name (e.g. 'Botox', 'Rhinoplasty', 'Microneedling')",
            },
        },
        "required": ["name"],
    },
}


async def run(inputs: dict, user_id: str) -> ToolResult:
    from app.db.client import get_client

    name = inputs["name"].strip()
    try:
        client = await get_client()
        result = (
            await client.table("procedures")
            .select(
                "id, name, category, description, is_surgical, "
                "recovery_duration_label, recovery_overview, "
                "what_is_normal, what_to_watch_for, "
                "who_its_for, default_consult_questions, editorial_summary"
            )
            .ilike("name", name)
            .limit(1)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return ToolResult(
                content={"found": False, "name": name},
                error=f"No procedure found matching '{name}'",
            )
        return ToolResult(content={"found": True, "procedure": result.data})
    except Exception as exc:
        return ToolResult(content={}, error=str(exc))
