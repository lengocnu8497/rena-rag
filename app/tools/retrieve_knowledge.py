from app.tools._types import ToolResult

DEFINITION = {
    "name": "retrieve_knowledge",
    "description": (
        "Search Rena's knowledge base (procedures, medical papers, guides, FAQs) "
        "for factual or clinical information. Use for questions about how a procedure "
        "works, what recovery looks like, evidence, risks, or aftercare."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query",
            },
            "procedure_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Limit results to specific procedures (e.g. ['botox', 'rhinoplasty'])",
            },
            "sections": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "description",
                        "editorial_summary",
                        "who_its_for",
                        "what_is_normal",
                        "what_to_watch_for",
                        "recovery_overview",
                        "consult_questions",
                    ],
                },
                "description": "Limit results to specific content sections",
            },
            "source_type": {
                "type": "string",
                "enum": ["procedure", "medical_paper", "guide", "faq"],
                "description": "Limit results to a specific content type",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (max 20, default 10)",
            },
        },
        "required": ["query"],
    },
}


async def run(inputs: dict, user_id: str) -> ToolResult:
    from app.retrieval.retriever import retrieve_chunks

    try:
        results = await retrieve_chunks(
            query=inputs["query"],
            procedure_tags=inputs.get("procedure_tags"),
            sections=inputs.get("sections"),
            source_type=inputs.get("source_type"),
            top_k=min(inputs.get("top_k", 10), 20),
        )
        return ToolResult(
            content={
                "count": len(results),
                "chunks": [
                    {
                        "id": r.id,
                        "source_name": r.source_name,
                        "source_type": r.source_type,
                        "section": r.section,
                        "procedure_tags": r.procedure_tags,
                        "paper_year": r.paper_year,
                        "content": r.content,
                        "similarity": round(r.similarity, 4),
                    }
                    for r in results
                ],
            }
        )
    except Exception as exc:
        return ToolResult(content={}, error=str(exc))
