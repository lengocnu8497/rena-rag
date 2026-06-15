"""
PDF ingestion endpoints for the React dashboard.

  POST /api/ingest/pdf/suggest  — upload a PDF, get AI-suggested sidecar fields
  POST /api/ingest/pdf          — upload a PDF + confirmed metadata, ingest it
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.client import upsert_chunks
from app.models.embedder import embed_batch
from app.models.orchestrator import HAIKU, classify
from app.retrieval.chunker import chunk_pdf

router = APIRouter(prefix="/api/ingest", tags=["internal"])
logger = logging.getLogger("rena.ingest_pdf")

VALID_PROCEDURES = [
    "rhinoplasty", "facelift", "blepharoplasty", "brow lift", "neck lift",
    "chin augmentation", "otoplasty", "breast augmentation", "breast lift",
    "breast reduction", "brazilian butt lift", "mommy makeover", "microneedling",
    "chemical peel", "laser resurfacing", "ipl photofacial", "hydrafacial",
    "ultherapy / hifu", "rf microneedling", "laser hair removal", "botox / dysport",
    "lip filler", "cheek filler", "jawline filler", "under eye filler",
    "dermal filler", "kybella", "sculptra", "prp / prf therapy", "coolsculpting",
    "emsculpt / emsculpt neo", "rf skin tightening", "pdo thread lift",
    "microfocused ultrasound", "liposuction", "tummy tuck", "fat transfer",
    "body contouring surgery",
]

_SUGGEST_SYSTEM = f"""\
You are a medical research librarian. Given the opening text of a PDF, extract \
bibliographic metadata and return ONLY a JSON object — no markdown, no explanation.

{{
  "source_name": "<Author(s) Year — Full Title>",
  "source_type": "medical_paper",
  "procedure_tags": ["<procedure>"],
  "paper_year": <year or null>
}}

Field rules:
- source_name: format as "LastName et al. YEAR — Title" (max 120 chars)
- source_type: one of medical_paper | guide | faq
- procedure_tags: choose ONLY from this exact list (spaces not underscores):
  {', '.join(VALID_PROCEDURES)}
  Include every procedure the paper primarily covers. Empty array if none apply.
- paper_year: four-digit integer or null if not found\
"""


def _extract_preview(pdf_bytes: bytes, max_chars: int = 3000) -> str:
    """Extract text from the first 3 pages of the PDF."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as f:
        f.write(pdf_bytes)
        f.flush()
        doc = fitz.open(f.name)
        pages = [doc[i].get_text() for i in range(min(3, len(doc)))]
        doc.close()
    return "\n\n".join(pages)[:max_chars]


class SidecarSuggestion(BaseModel):
    source_name: str
    source_type: str
    procedure_tags: list[str]
    paper_year: int | None
    preview_text: str  # first ~500 chars shown in UI for context


@router.post("/pdf/suggest", response_model=SidecarSuggestion)
async def suggest_sidecar(file: UploadFile) -> SidecarSuggestion:
    """
    Extract the first 3 pages of a PDF and ask Haiku to suggest sidecar fields.
    Returns pre-filled metadata the user can review before ingesting.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:  # 50 MB hard cap
        raise HTTPException(status_code=413, detail="PDF must be under 50 MB.")

    preview = _extract_preview(pdf_bytes)
    if not preview.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF — it may be scanned/image-only.")

    raw = await classify(
        prompt=f"{_SUGGEST_SYSTEM}\n\nPDF opening text:\n{preview}",
        model=HAIKU,
        max_tokens=400,
    )

    try:
        data: dict[str, Any] = json.loads(raw.strip())
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group()) if m else {}

    return SidecarSuggestion(
        source_name=str(data.get("source_name") or file.filename.removesuffix(".pdf")),
        source_type=str(data.get("source_type") or "medical_paper"),
        procedure_tags=[
            t.lower() for t in (data.get("procedure_tags") or [])
            if isinstance(t, str) and t.lower() in VALID_PROCEDURES
        ],
        paper_year=int(data["paper_year"]) if data.get("paper_year") else None,
        preview_text=preview[:500],
    )


@router.post("/pdf")
async def ingest_pdf(
    file: UploadFile,
    source_name: str = Form(...),
    source_type: str = Form(...),
    procedure_tags: str = Form(...),   # JSON-encoded list: '["rhinoplasty"]'
    paper_year: str = Form(""),
) -> dict[str, Any]:
    """
    Ingest a single PDF with confirmed sidecar metadata.
    Accepts multipart/form-data with the PDF file + metadata fields.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    pdf_bytes = await file.read()

    try:
        tags: list[str] = json.loads(procedure_tags)
    except json.JSONDecodeError:
        tags = []

    year: int | None = int(paper_year) if paper_year.isdigit() else None

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp_path = Path(f.name)

    try:
        chunks = chunk_pdf(
            path=tmp_path,
            source_name=source_name,
            source_type=source_type,
            procedure_tags=tags,
            paper_year=year,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if not chunks:
        raise HTTPException(status_code=422, detail="No text could be extracted from the PDF.")

    texts = [c["content"] for c in chunks]
    embeddings = await embed_batch(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb

    await upsert_chunks(chunks)

    logger.info("ingest_pdf: %s → %d chunks", source_name, len(chunks))
    return {
        "status": "ok",
        "source_name": source_name,
        "chunks_added": len(chunks),
    }
