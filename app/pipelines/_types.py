from __future__ import annotations

from dataclasses import dataclass, field

from app.retrieval.router import RouteDecision


@dataclass
class PipelineResult:
    response: str
    route: RouteDecision
    pipeline_mode: str              # "deterministic" | "agent"
    chunk_ids: list[str]
    source_names: list[str]
    mean_retrieval_score: float | None
    tools_called: list[str]         # empty for deterministic
    model_generation: str
    chunk_contents: list[str] = field(default_factory=list)  # for faithfulness scoring
    model_routing: str = "claude-haiku-4-5-20251001"
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
