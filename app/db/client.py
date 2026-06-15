"""
Async Supabase client — singleton, initialized at app startup.

All methods use the service role key (bypasses RLS).
Vector search is done via RPC functions defined in the DB migration
(PostgREST query builder does not support pgvector <=> operator).
"""

from __future__ import annotations

from typing import Any, cast

from supabase import AsyncClient, acreate_client

from app.config import settings

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_client: AsyncClient | None = None


async def init_client() -> None:
    """Call once at app startup (lifespan hook)."""
    global _client
    _client = await acreate_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


async def get_client() -> AsyncClient:
    if _client is None:
        raise RuntimeError("DB client not initialized — call init_client() at startup")
    return _client


# ---------------------------------------------------------------------------
# User data helpers
# ---------------------------------------------------------------------------

async def get_user_profile(user_id: str) -> dict[str, Any] | None:
    client = await get_client()
    result = (
        await client.table("user_profiles")
        .select(
            "full_name, gender, age_range, race_ethnicity, "
            "aesthetic_goals, procedures_of_interest, previous_procedures, "
            "health_flags, body_areas_of_interest, "
            "subscription_tier, subscription_status, subscription_current_period_end"
        )
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return cast(dict[str, Any] | None, result.data if result is not None else None)


async def get_journal_entries(user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    client = await get_client()
    result = (
        await client.table("journal_entries")
        .select(
            "procedure_name, day_number, entry_date, notes, "
            "pain_index, swelling_index, bruising_index, redness_index, overall_score, summary"
        )
        .eq("user_id", user_id)
        .order("entry_date", desc=True)
        .limit(limit)
        .execute()
    )
    return cast(list[dict[str, Any]], result.data or [])


async def get_recovery_plan(user_id: str) -> dict[str, Any] | None:
    client = await get_client()
    result = (
        await client.table("user_recovery_plan_cache")
        .select(
            "procedure_id, procedure_name, procedure_date, generated_at, "
            "current_phase_id, current_phase_title, current_phase_status, "
            "current_phase_summary, current_phase_focus_areas, personalization_summary"
        )
        .eq("user_id", user_id)
        .order("generated_at", desc=True)
        .limit(1)
        .maybe_single()
        .execute()
    )
    return cast(dict[str, Any] | None, result.data if result is not None else None)


async def get_all_procedures() -> list[dict[str, Any]]:
    """Used by the ingestion pipeline to seed knowledge_chunks."""
    client = await get_client()
    result = (
        await client.table("procedures")
        .select(
            "id, name, category, description, recovery_duration_label, is_surgical, "
            "recovery_overview, what_is_normal, what_to_watch_for, "
            "who_its_for, default_consult_questions, editorial_summary"
        )
        .order("sort_order", desc=False)
        .execute()
    )
    return cast(list[dict[str, Any]], result.data or [])


# ---------------------------------------------------------------------------
# Knowledge chunk helpers (ingestion)
# ---------------------------------------------------------------------------

async def upsert_chunks(chunks: list[dict[str, Any]]) -> None:
    """
    Upsert knowledge chunks with their embeddings.
    Each chunk dict must include all knowledge_chunks columns.
    Upsert key: (source_name, chunk_index) — safe to re-run ingestion.
    """
    client = await get_client()
    await (
        client.table("knowledge_chunks")
        .upsert(chunks, on_conflict="source_name,chunk_index")
        .execute()
    )


# ---------------------------------------------------------------------------
# Vector search — calls RPC functions defined in the migration
# ---------------------------------------------------------------------------

async def vector_search_chunks(
    embedding: list[float],
    procedure_tags: list[str] | None = None,
    section: list[str] | None = None,
    source_type: str | None = None,
    top_k: int = 20,
    min_score: float = 0.65,
) -> list[dict[str, Any]]:
    """
    ANN search over knowledge_chunks with optional metadata pre-filters.
    Returns rows sorted by cosine similarity descending, score >= min_score.
    """
    client = await get_client()
    result = await client.rpc(
        "match_knowledge_chunks",
        {
            "query_embedding": embedding,
            "filter_procedure_tags": procedure_tags or [],
            "filter_sections": section or [],
            "filter_source_type": source_type,
            "match_count": top_k,
            "min_similarity": min_score,
        },
    ).execute()
    return cast(list[dict[str, Any]], result.data or [])


async def vector_search_memory(
    user_id: str,
    embedding: list[float],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Semantic search over this user's past conversation summaries."""
    client = await get_client()
    result = await client.rpc(
        "match_conversation_memory",
        {
            "p_user_id": user_id,
            "query_embedding": embedding,
            "match_count": top_k,
        },
    ).execute()
    return cast(list[dict[str, Any]], result.data or [])


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

async def save_conversation_memory(
    user_id: str,
    conversation_id: str | None,
    summary: str,
    embedding: list[float],
    procedures_discussed: list[str],
) -> None:
    client = await get_client()
    await (
        client.table("conversation_memory")
        .insert(
            {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "summary": summary,
                "embedding": embedding,
                "procedures_discussed": procedures_discussed,
            }
        )
        .execute()
    )


# ---------------------------------------------------------------------------
# Eval logging
# ---------------------------------------------------------------------------

async def insert_eval_log(log: dict[str, Any]) -> None:
    client = await get_client()
    await client.table("rag_eval_logs").insert(log).execute()
