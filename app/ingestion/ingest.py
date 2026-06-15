"""
Ingestion pipeline — seeds knowledge_chunks from procedures and PDFs.

Usage:
  uv run python -m app.ingestion.ingest                        # procedures only
  uv run python -m app.ingestion.ingest --pdf-dir /path/pdfs  # + PDFs

PDF directory convention: each PDF must have a JSON sidecar with the same
stem, e.g. botox_study.pdf + botox_study.json:

  {
    "source_name": "Smith et al. 2023 — Botox Longevity",
    "source_type": "medical_paper",
    "procedure_tags": ["botox"],
    "paper_year": 2023
  }

PDFs without a sidecar are skipped with a warning.
Re-running is safe — upsert on (source_name, chunk_index) is idempotent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from app.db.client import get_all_procedures, init_client, upsert_chunks
from app.models.embedder import embed_batch
from app.retrieval.chunker import chunk_pdf, chunk_procedure

EMBED_BATCH_SIZE = 100   # stay well under OpenAI rate limits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _embed_in_batches(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        print(
            f"  embedding batch {i // EMBED_BATCH_SIZE + 1}"
            f"/{-(-len(texts) // EMBED_BATCH_SIZE)}"
            f" ({len(batch)} texts)…"
        )
        embeddings.extend(await embed_batch(batch))
    return embeddings


def _attach_embeddings(
    chunks: list[dict[str, Any]], embeddings: list[list[float]]
) -> list[dict[str, Any]]:
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb
    return chunks


# ---------------------------------------------------------------------------
# Procedure ingestion
# ---------------------------------------------------------------------------

async def ingest_procedures() -> int:
    """Chunk + embed + upsert all rows from the procedures table."""
    print("Fetching procedures…")
    procedures = await get_all_procedures()
    if not procedures:
        print("  No procedures found — is the DB populated?")
        return 0

    print(f"  Found {len(procedures)} procedures. Chunking…")
    chunks: list[dict[str, Any]] = []
    for proc in procedures:
        proc_chunks = chunk_procedure(proc)
        chunks.extend(proc_chunks)
        print(f"  {proc['name']}: {len(proc_chunks)} chunks")

    print(f"\nEmbedding {len(chunks)} chunks…")
    embed_texts = [c.pop("embed_text", c["content"]) for c in chunks]
    embeddings = await _embed_in_batches(embed_texts)
    _attach_embeddings(chunks, embeddings)

    print("Upserting…")
    await upsert_chunks(chunks)
    print(f"Done — {len(chunks)} procedure chunks upserted.\n")
    return len(chunks)


# ---------------------------------------------------------------------------
# PDF ingestion
# ---------------------------------------------------------------------------

def _load_sidecar(pdf_path: Path) -> dict[str, Any] | None:
    sidecar = pdf_path.with_suffix(".json")
    if not sidecar.exists():
        print(f"  WARNING: no sidecar for {pdf_path.name} — skipping")
        return None
    try:
        data = json.loads(sidecar.read_text())
        required = {"source_name", "source_type", "procedure_tags"}
        missing = required - data.keys()
        if missing:
            print(f"  WARNING: sidecar {sidecar.name} missing {missing} — skipping")
            return None
        return data
    except json.JSONDecodeError as exc:
        print(f"  WARNING: invalid JSON in {sidecar.name}: {exc} — skipping")
        return None


async def ingest_pdf_dir(directory: Path) -> int:
    pdfs = sorted(directory.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {directory}")
        return 0

    total = 0
    for pdf_path in pdfs:
        print(f"Processing {pdf_path.name}…")
        meta = _load_sidecar(pdf_path)
        if meta is None:
            continue

        chunks = chunk_pdf(
            path=pdf_path,
            source_name=meta["source_name"],
            source_type=meta["source_type"],
            procedure_tags=meta["procedure_tags"],
            paper_year=meta.get("paper_year"),
        )
        if not chunks:
            print(f"  No text extracted from {pdf_path.name} — skipping")
            continue

        print(f"  {len(chunks)} chunks. Embedding…")
        embeddings = await _embed_in_batches([c["content"] for c in chunks])
        _attach_embeddings(chunks, embeddings)

        await upsert_chunks(chunks)
        print(f"  Upserted {len(chunks)} chunks for {meta['source_name']}\n")
        total += len(chunks)

    return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main(pdf_dir: Path | None) -> None:
    await init_client()

    proc_count = await ingest_procedures()

    pdf_count = 0
    if pdf_dir:
        print(f"Processing PDFs in {pdf_dir}…\n")
        pdf_count = await ingest_pdf_dir(pdf_dir)

    print(
        f"Ingestion complete — "
        f"{proc_count} procedure chunks, {pdf_count} PDF chunks."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rena RAG ingestion pipeline")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=None,
        help="Directory of PDFs to ingest (each needs a .json sidecar)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.pdf_dir))
