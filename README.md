# rena-rag

Agentic RAG service for the Rena iOS app. Replaces the `chat-ai` Supabase Edge Function with a FastAPI + pgvector + Anthropic Claude pipeline running on AWS ECS/Fargate.

## Architecture

```
iOS → POST /chat → rena-rag (ECS)
                     ├── Router (Haiku)      — intent + pipeline selection
                     ├── Rewriter (Haiku)    — retrieval-optimised query
                     ├── Retriever           — pgvector ANN search (Supabase RPC)
                     ├── Reranker (Haiku)    — cross-attention relevance scoring
                     ├── Context assembler   — structured system prompt
                     └── Generator (Sonnet)  — final response + tool calls
```

## Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Docker (for local dev)
- Supabase project with migrations applied (see below)
- Anthropic API key, OpenAI API key

## Setup

```bash
cp .env.example .env   # fill in all values
uv sync
```

`.env` required keys:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

## Local dev

```bash
docker compose up
# or without Docker:
uv run uvicorn app.main:app --reload
```

Health check: `curl http://localhost:8000/health`

## Supabase migrations

Three migrations must be applied to the Supabase project before running ingestion or serving requests.

```bash
cd "renaissance-mobile/Renaissance Mobile"
supabase db push
```

Or apply manually in the Supabase SQL editor in order:

| File | What it creates |
|---|---|
| `20260613000001_rag_knowledge_and_memory.sql` | `knowledge_chunks`, `conversation_memory`, pgvector extension |
| `20260613000002_rag_eval_logs.sql` | `rag_eval_logs` |
| `20260613000003_rag_vector_search_functions.sql` | `match_knowledge_chunks()`, `match_conversation_memory()` RPC functions |

## Ingestion

The ingestion pipeline chunks and embeds content into `knowledge_chunks`. Run it once after deploying migrations, and re-run whenever procedure content changes.

### Procedures (required — run first)

Seeds `knowledge_chunks` from every row in the `procedures` table. Safe to re-run — uses upsert on `(source_name, chunk_index)`.

```bash
uv run python -m app.ingestion.ingest
```

Expected output:
```
Fetching procedures…
  Found 30 procedures. Chunking…
  Botox: 7 chunks
  Rhinoplasty: 7 chunks
  ...
Embedding 210 chunks…
  embedding batch 1/3 (100 texts)…
  embedding batch 2/3 (100 texts)…
  embedding batch 3/3 (10 texts)…
Upserting…
Done — 210 procedure chunks upserted.
```

### PDFs (optional — medical papers, guides, FAQs)

Place PDFs in a directory. Each PDF needs a JSON sidecar file with the same stem:

```
/papers/
  botox_longevity_2023.pdf
  botox_longevity_2023.json   ← required
  rhinoplasty_outcomes.pdf
  rhinoplasty_outcomes.json
```

Sidecar format:
```json
{
  "source_name": "Smith et al. 2023 — Botox Longevity Study",
  "source_type": "medical_paper",
  "procedure_tags": ["botox"],
  "evidence_grade": "A",
  "paper_year": 2023
}
```

`source_type` must be one of: `medical_paper`, `guide`, `faq`.

Run ingestion with the PDF directory:
```bash
uv run python -m app.ingestion.ingest --pdf-dir /path/to/papers
```

PDFs without a sidecar are skipped with a warning. Re-running is safe.

### Re-ingesting after procedure content changes

```bash
uv run python -m app.ingestion.ingest
```

Changed chunks are updated in-place. Chunks whose `(source_name, chunk_index)` no longer exist (e.g. a section was removed) are left in the table — delete them manually if needed.

## Dashboard

Internal engineering dashboard for observability and debugging. Built with Vite + React + TypeScript + Tailwind. Requires the FastAPI service to be running.

```bash
cd dashboard
npm install
npm run dev   # http://localhost:5173
```

Pages:

| Page | URL | What it shows |
|---|---|---|
| Eval Results | `/` | Per-request quality table from `rag_eval_logs` — faithfulness, retrieval sim, latency, cost |
| Retrieval Inspector | `/inspector` | Full pipeline trace for any query: route → rewrite → chunks → reranked → response |
| Knowledge Base | `/knowledge` | Browse, search, filter, and delete entries in `knowledge_chunks` |
| Ingestion | `/ingestion` | One-click procedure re-seed + CLI reference |
| Cost Dashboard | `/costs` | Recharts daily spend by model (Sonnet / Haiku / embeddings) + latency trend |

The Vite dev server proxies `/api/*` to `http://localhost:8000`, so no CORS configuration is needed locally.

To kill a stuck process on port 8000:
```bash
lsof -ti :8000 | xargs kill -9
```

## API

### `GET /health`
```json
{"status": "ok", "service": "rena-rag", "environment": "development"}
```

### `POST /chat`
```
Authorization: Bearer <supabase-user-jwt>
Content-Type: application/json
```
```json
{
  "query": "Is my face supposed to be puffy after Botox?",
  "conversation_history": [
    {"role": "user", "content": "I just got Botox yesterday"},
    {"role": "assistant", "content": "How are you feeling?"}
  ],
  "conversation_id": "optional-uuid"
}
```
Response:
```json
{
  "response": "Mild puffiness for 24-48 hours is completely normal after Botox...",
  "conversation_id": "uuid",
  "pipeline_mode": "deterministic",
  "tools_called": [],
  "latency_ms": 1243
}
```

### Internal dashboard endpoints (no auth)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/inspect` | Full retrieval trace — route, rewrite, pre/post-rerank chunks, response |
| `GET` | `/api/eval-logs` | Paginated `rag_eval_logs` (`?intent=&pipeline_mode=&scope_blocked=`) |
| `GET` | `/api/chunks` | Browse `knowledge_chunks` (`?procedure=&section=&source_type=&search=`) |
| `DELETE` | `/api/chunks/{id}` | Remove a specific chunk |
| `GET` | `/api/cost-summary` | Daily cost/token aggregates by model (`?days=30`) |
| `GET` | `/api/chunk-stats` | Aggregate counts by source, section, and procedure |
| `POST` | `/api/ingest` | Trigger procedure ingestion in the background |

## Observability

Every request is logged as structured JSON to stdout (CloudWatch-compatible):
```json
{"ts": "2026-06-14T07:00:00Z", "level": "INFO", "logger": "rena.request",
 "msg": "POST /chat 200", "request_id": "...", "latency_ms": 1243}
```

Every `/chat` response writes a row to `rag_eval_logs` (background task, non-blocking) including faithfulness and relevance scores from Haiku.
