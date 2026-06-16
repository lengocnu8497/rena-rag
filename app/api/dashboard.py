"""
Internal dashboard API — data endpoints for the React engineering dashboard.

  GET  /api/eval-logs      — paginated rag_eval_logs with optional filters
  GET  /api/chunks         — paginated knowledge_chunks with search/filter
  DELETE /api/chunks/{id}  — remove a specific chunk
  GET  /api/cost-summary   — daily cost aggregation for the chart
  GET  /api/chunk-stats    — aggregate counts by procedure / section / source_type
  POST /api/ingest         — trigger procedure ingestion pipeline

No auth: internal engineering tool only.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.client import get_client

router = APIRouter(prefix="/api", tags=["internal"])
logger = logging.getLogger("rena.dashboard")


# ---------------------------------------------------------------------------
# Eval logs
# ---------------------------------------------------------------------------

@router.get("/eval-logs")
async def list_eval_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    intent: str | None = None,
    pipeline_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    scope_blocked: bool | None = None,
) -> dict[str, Any]:
    client = await get_client()
    q = (
        client.table("rag_eval_logs")
        .select(
            "id,created_at,query,intent,pipeline_mode,mean_retrieval_score,"
            "faithfulness_score,latency_ms,cost_usd,scope_blocked,"
            "model_generation,tokens_input,tokens_output,retrieved_sources"
        )
        .order("created_at", desc=True)
        .limit(limit)
        .offset(offset)
    )
    if intent:
        q = q.eq("intent", intent)
    if pipeline_mode:
        q = q.eq("pipeline_mode", pipeline_mode)
    if date_from:
        q = q.gte("created_at", date_from)
    if date_to:
        q = q.lte("created_at", date_to)
    if scope_blocked is not None:
        q = q.eq("scope_blocked", scope_blocked)

    result = await q.execute()
    return {"data": result.data, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Knowledge chunks
# ---------------------------------------------------------------------------

@router.get("/chunks")
async def list_chunks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    procedure: str | None = None,
    section: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    client = await get_client()
    q = (
        client.table("knowledge_chunks")
        .select(
            "id,source_type,source_name,section,procedure_tags,"
            "paper_year,content,created_at"
        )
        .order("source_name")
        .limit(limit)
        .offset(offset)
    )
    if procedure:
        q = q.contains("procedure_tags", [procedure])
    if section:
        q = q.eq("section", section)
    if source_type:
        q = q.eq("source_type", source_type)
    if search:
        q = q.ilike("content", f"%{search}%")

    result = await q.execute()
    return {"data": result.data, "limit": limit, "offset": offset}


@router.delete("/chunks/{chunk_id}")
async def delete_chunk(chunk_id: str) -> dict[str, str]:
    client = await get_client()
    result = await client.table("knowledge_chunks").delete().eq("id", chunk_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {"deleted": chunk_id}


# ---------------------------------------------------------------------------
# Cost summary
# ---------------------------------------------------------------------------

@router.get("/cost-summary")
async def cost_summary(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    """
    Return daily cost/token aggregates for the Recharts cost dashboard.
    Grouped by date and model_generation.
    """
    client = await get_client()
    result = await (
        client.table("rag_eval_logs")
        .select(
            "created_at,model_generation,cost_usd,tokens_input,tokens_output,latency_ms"
        )
        .order("created_at", desc=True)
        .limit(days * 500)  # rough upper bound: 500 requests/day
        .execute()
    )

    # Group by date × model in Python (avoids raw SQL dependency)
    from collections import defaultdict

    daily: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"date": "", "sonnet_cost": 0.0, "haiku_cost": 0.0,
                 "embed_cost": 0.0, "total_cost": 0.0,
                 "requests": 0, "mean_latency_ms": 0, "_latencies": []}
    )

    for row in cast(list[dict[str, Any]], result.data or []):
        date = (row.get("created_at") or "")[:10]
        if not date:
            continue
        model = row.get("model_generation") or "unknown"
        cost = float(row.get("cost_usd") or 0)
        daily[date]["date"] = date
        daily[date]["total_cost"] = round(daily[date]["total_cost"] + cost, 6)
        daily[date]["requests"] += 1
        daily[date]["_latencies"].append(row.get("latency_ms") or 0)
        if "sonnet" in model:
            daily[date]["sonnet_cost"] = round(daily[date]["sonnet_cost"] + cost, 6)
        elif "haiku" in model:
            daily[date]["haiku_cost"] = round(daily[date]["haiku_cost"] + cost, 6)
        else:
            daily[date]["embed_cost"] = round(daily[date]["embed_cost"] + cost, 6)

    rows = []
    for d in sorted(daily.values(), key=lambda x: x["date"]):
        lats = d.pop("_latencies")
        d["mean_latency_ms"] = int(sum(lats) / len(lats)) if lats else 0
        rows.append(d)

    return {"data": rows[-days:]}


# ---------------------------------------------------------------------------
# Chunk stats
# ---------------------------------------------------------------------------

@router.get("/chunk-stats")
async def chunk_stats() -> dict[str, Any]:
    """Aggregate chunk counts for the KnowledgeBase overview."""
    client = await get_client()
    result = await (
        client.table("knowledge_chunks")
        .select("source_type,section,procedure_tags")
        .execute()
    )

    from collections import Counter

    by_source: Counter[str] = Counter()
    by_section: Counter[str] = Counter()
    by_procedure: Counter[str] = Counter()

    for row in cast(list[dict[str, Any]], result.data or []):
        by_source[row.get("source_type") or "unknown"] += 1
        by_section[row.get("section") or "unknown"] += 1
        for tag in row.get("procedure_tags") or []:
            by_procedure[tag] += 1

    return {
        "total": len(result.data or []),
        "by_source": dict(by_source.most_common()),
        "by_section": dict(by_section.most_common()),
        "by_procedure": dict(by_procedure.most_common(20)),
    }


# ---------------------------------------------------------------------------
# Ingestion trigger
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    source: str = "procedures"  # only "procedures" supported via API


@router.post("/ingest")
async def trigger_ingest(req: IngestRequest) -> dict[str, Any]:
    """Trigger procedure ingestion in the background and return immediately."""
    if req.source != "procedures":
        raise HTTPException(status_code=400, detail="Only source='procedures' is supported via the API.")

    from app.db.client import init_client as _ensure_client
    from app.ingestion.ingest import ingest_procedures

    async def _run() -> None:
        await _ensure_client()
        count = await ingest_procedures()
        logger.info("dashboard_ingest: %d chunks upserted", count)

    asyncio.create_task(_run())
    return {"status": "started", "message": "Ingestion running in background — refresh the Knowledge Base page in ~30s."}
