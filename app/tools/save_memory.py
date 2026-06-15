from app.tools._types import ToolResult

DEFINITION = {
    "name": "save_memory",
    "description": (
        "Persist a summary of this conversation to the user's long-term memory. "
        "Call at the end of a substantive conversation so future sessions can "
        "recall what was discussed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-4 sentence summary of the key topics covered",
            },
            "procedures_discussed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Procedure names mentioned in this conversation",
            },
            "conversation_id": {
                "type": "string",
                "description": "Optional conversation UUID for grouping turns",
            },
        },
        "required": ["summary"],
    },
}


async def run(inputs: dict, user_id: str) -> ToolResult:
    from app.db.client import save_conversation_memory
    from app.models.embedder import embed

    try:
        summary = inputs["summary"]
        embedding = await embed(summary)
        await save_conversation_memory(
            user_id=user_id,
            conversation_id=inputs.get("conversation_id"),
            summary=summary,
            embedding=embedding,
            procedures_discussed=inputs.get("procedures_discussed", []),
        )
        return ToolResult(content={"saved": True, "summary_length": len(summary)})
    except Exception as exc:
        return ToolResult(content={}, error=str(exc))
