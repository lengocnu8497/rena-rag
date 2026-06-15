"""
Text chunking for the ingestion pipeline.

chunk_procedure: splits a procedures row into per-section chunks.
chunk_pdf:       extracts text from a PDF with PyMuPDF and applies a
                 sliding-window token split.

Both return list[dict] ready for upsert into knowledge_chunks
(no 'embedding' key — the ingestion pipeline adds that separately).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import tiktoken

# cl100k_base matches text-embedding-3-small tokenisation
_ENC = tiktoken.get_encoding("cl100k_base")

MAX_CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50

# Ordered list of (db_field, section label) for procedure rows.
# Fields that may be lists (consult_questions) are joined before chunking.
_PROCEDURE_SECTIONS: list[tuple[str, str]] = [
    ("description", "description"),
    ("editorial_summary", "editorial_summary"),
    ("who_its_for", "who_its_for"),
    ("what_is_normal", "what_is_normal"),
    ("what_to_watch_for", "what_to_watch_for"),
    ("recovery_overview", "recovery_overview"),
    ("default_consult_questions", "consult_questions"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_text(text: str) -> list[str]:
    """Sliding-window token split. Returns at least one chunk even if empty."""
    tokens = _ENC.encode(text)
    if not tokens:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + MAX_CHUNK_TOKENS, len(tokens))
        chunks.append(_ENC.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - OVERLAP_TOKENS
    return chunks


def _field_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(v) for v in value if v)
    return str(value).strip() if value else ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_procedure(procedure: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Produce knowledge_chunk dicts from a single procedures row.
    One chunk per section; long sections are split with overlap.
    """
    name: str = procedure["name"]
    tags = [name.lower()]
    category: str | None = procedure.get("category")
    source_id: str | None = procedure.get("id")

    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for field, section_label in _PROCEDURE_SECTIONS:
        text = _field_text(procedure.get(field))
        if not text:
            continue
        for sub in _split_text(text):
            chunks.append(
                {
                    "source_type": "procedure",
                    "source_id": source_id,
                    "source_name": name,
                    "chunk_index": chunk_index,
                    "section": section_label,
                    "procedure_tags": tags,
                    "paper_year": None,
                    "content": sub,
                    # embed_text anchors the vector to procedure+section space;
                    # removed before upsert so stored content stays clean.
                    "embed_text": f"{name.lower()} {section_label}: {sub}",
                    "metadata": {"procedure_category": category},
                }
            )
            chunk_index += 1

    return chunks


def chunk_pdf(
    path: str | Path,
    source_name: str,
    source_type: str,
    procedure_tags: list[str],
    paper_year: int | None = None,
) -> list[dict[str, Any]]:
    """
    Extract text from a PDF and split into overlapping token chunks.

    source_type should be one of: 'medical_paper', 'guide', 'faq'.
    """
    doc = fitz.open(str(path))
    # Join pages with a blank line so paragraph boundaries are preserved
    full_text = "\n\n".join(page.get_text() for page in doc)
    doc.close()

    return [
        {
            "source_type": source_type,
            "source_id": None,
            "source_name": source_name,
            "chunk_index": i,
            "section": None,
            "procedure_tags": procedure_tags,
            "paper_year": paper_year,
            "content": sub,
            "metadata": {},
        }
        for i, sub in enumerate(_split_text(full_text))
    ]
