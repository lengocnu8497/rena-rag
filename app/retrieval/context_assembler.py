"""
Context assembler — formats retrieved content into a system prompt.

assemble(chunks, user_context, memories) → AssembledContext

Used by the deterministic pipeline (one-shot) and as the base system prompt
for the agent loop. AssembledContext.chunk_ids / source_names feed rag_eval_logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.retrieval.retriever import ChunkResult, MemoryResult

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

MAX_CHUNKS = 8          # chunks injected into context
CHUNK_PREVIEW = 600     # chars per chunk (truncated with ellipsis)
JOURNAL_LIMIT = 3       # most-recent journal entries shown
MEMORY_LIMIT = 2        # past conversation summaries shown

# ---------------------------------------------------------------------------
# Rena base persona
# ---------------------------------------------------------------------------

_BASE_SYSTEM = """\
You are Rena, a warm and knowledgeable AI assistant specialising in aesthetic \
procedures and post-procedure recovery. You help users understand their \
treatment, track their healing, and prepare for consultations.

Guidelines:
- Ground every clinical claim in the knowledge provided below; do not invent \
medical facts.
- Be empathetic and supportive — recovery can be anxious for users.
- When a concern sounds urgent (severe pain, fever, unexpected asymmetry, \
difficulty swallowing), advise the user to contact their provider immediately.
- Never diagnose, prescribe, or replace professional medical advice.
- Stay strictly within scope: aesthetic procedures, skincare, and recovery. \
Decline unrelated requests politely.\
"""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AssembledContext:
    system_prompt: str
    chunk_ids: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _fmt_chunks(chunks: list[ChunkResult]) -> str:
    if not chunks:
        return ""
    lines = ["## Knowledge Base\n"]
    for c in chunks[:MAX_CHUNKS]:
        header = f"[{c.source_name}"
        if c.section:
            header += f" › {c.section}"
        header += f" | similarity {c.similarity:.2f}]"
        preview = c.content[:CHUNK_PREVIEW]
        if len(c.content) > CHUNK_PREVIEW:
            preview += "…"
        lines.append(f"{header}\n{preview}\n")
    return "\n".join(lines)


def _fmt_profile(profile: dict[str, Any] | None) -> str:
    if not profile:
        return ""
    parts: list[str] = ["## User Profile\n"]
    if profile.get("full_name"):
        parts.append(f"Name: {profile['full_name']}")
    if profile.get("age_range"):
        parts.append(f"Age range: {profile['age_range']}")
    if profile.get("aesthetic_goals"):
        parts.append(f"Goals: {profile['aesthetic_goals']}")
    if profile.get("previous_procedures"):
        parts.append(f"Previous procedures: {profile['previous_procedures']}")
    if profile.get("health_flags"):
        parts.append(f"Health flags: {profile['health_flags']}")
    return "\n".join(parts)


def _fmt_recovery(recovery: dict[str, Any] | None) -> str:
    if not recovery:
        return ""
    lines = ["## Active Recovery Plan\n"]
    if recovery.get("procedure_name"):
        lines.append(f"Procedure: {recovery['procedure_name']}")
    if recovery.get("procedure_date"):
        lines.append(f"Date: {recovery['procedure_date']}")
    if recovery.get("current_phase_title"):
        lines.append(f"Phase: {recovery['current_phase_title']}")
    if recovery.get("current_phase_status"):
        lines.append(f"Status: {recovery['current_phase_status']}")
    if recovery.get("current_phase_summary"):
        lines.append(f"Summary: {recovery['current_phase_summary']}")
    if recovery.get("current_phase_focus_areas"):
        lines.append(f"Focus areas: {recovery['current_phase_focus_areas']}")
    if recovery.get("personalization_summary"):
        lines.append(f"Notes: {recovery['personalization_summary']}")
    return "\n".join(lines)


def _fmt_journal(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return ""
    lines = ["## Recent Journal\n"]
    for e in entries[:JOURNAL_LIMIT]:
        date = e.get("entry_date", "")
        day = f"Day {e['day_number']}" if e.get("day_number") else ""
        proc = e.get("procedure_name", "")
        header = " | ".join(filter(None, [proc, day, date]))
        scores = []
        for key in ("pain_index", "swelling_index", "bruising_index", "overall_score"):
            if e.get(key) is not None:
                scores.append(f"{key.replace('_index','').replace('_score',' score')}: {e[key]}")
        note = e.get("notes") or e.get("summary") or ""
        line = header
        if scores:
            line += f"\n  {' | '.join(scores)}"
        if note:
            line += f"\n  {note[:200]}"
        lines.append(line)
    return "\n".join(lines)


def _fmt_memories(memories: list[MemoryResult]) -> str:
    if not memories:
        return ""
    lines = ["## Past Conversations\n"]
    for m in memories[:MEMORY_LIMIT]:
        date = m.created_at[:10] if m.created_at else ""
        procs = (
            f" [{', '.join(m.procedures_discussed)}]" if m.procedures_discussed else ""
        )
        lines.append(f"[{date}]{procs} {m.summary}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assemble(
    chunks: list[ChunkResult],
    user_context: dict[str, Any] | None = None,
    memories: list[MemoryResult] | None = None,
) -> AssembledContext:
    """
    Build a structured system prompt from retrieved content.

    user_context: dict with keys 'profile', 'journal_entries', 'recovery_plan'
                  (shape returned by the get_user_context tool).
    memories:     list[MemoryResult] from retrieve_memory.
    """
    profile = (user_context or {}).get("profile")
    journal = (user_context or {}).get("journal_entries", [])
    recovery = (user_context or {}).get("recovery_plan")

    sections = [_BASE_SYSTEM]

    knowledge = _fmt_chunks(chunks)
    if knowledge:
        sections.append(knowledge)

    profile_block = _fmt_profile(profile)
    if profile_block:
        sections.append(profile_block)

    recovery_block = _fmt_recovery(recovery)
    if recovery_block:
        sections.append(recovery_block)

    journal_block = _fmt_journal(journal)
    if journal_block:
        sections.append(journal_block)

    memory_block = _fmt_memories(memories or [])
    if memory_block:
        sections.append(memory_block)

    return AssembledContext(
        system_prompt="\n\n".join(sections),
        chunk_ids=[c.id for c in chunks[:MAX_CHUNKS]],
        source_names=list(dict.fromkeys(c.source_name for c in chunks[:MAX_CHUNKS])),
    )
