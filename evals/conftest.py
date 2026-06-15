"""
Shared pytest fixtures for the eval suite.

All tests are integration tests — they hit real Supabase, Anthropic, and OpenAI
APIs. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, and SUPABASE_* in .env before running.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from app.db.client import init_client  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _init_db() -> None:
    await init_client()


@pytest.fixture(scope="session")
def golden() -> list[dict[str, Any]]:
    path = Path(__file__).parent / "golden_dataset.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="session")
def in_scope_cases(golden: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in golden if not c["should_block"]]


@pytest.fixture(scope="session")
def scope_gate_cases(golden: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in golden if c["should_block"]]
