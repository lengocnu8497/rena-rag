from app.tools._types import ToolResult

DEFINITION = {
    "name": "recall_memory",
    "description": (
        "Search this user's past conversation summaries for relevant prior context. "
        "Use when the user references something they asked about before, or when "
        "continuity with a previous session would improve the answer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in past conversations",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of memory entries to retrieve (default 3, max 5)",
            },
        },
        "required": ["query"],
    },
}


async def run(inputs: dict, user_id: str) -> ToolResult:
    from app.retrieval.retriever import retrieve_memory

    try:
        results = await retrieve_memory(
            user_id=user_id,
            query=inputs["query"],
            top_k=min(inputs.get("top_k", 3), 5),
        )
        return ToolResult(
            content={
                "count": len(results),
                "memories": [
                    {
                        "id": r.id,
                        "summary": r.summary,
                        "procedures_discussed": r.procedures_discussed,
                        "similarity": round(r.similarity, 4),
                        "created_at": r.created_at,
                    }
                    for r in results
                ],
            }
        )
    except Exception as exc:
        return ToolResult(content={}, error=str(exc))
