"""
Tool registry — single source of truth for definitions and dispatch.

Usage:
    from app.tools import TOOL_DEFINITIONS, dispatch

    # Pass to Anthropic API:
    tools=TOOL_DEFINITIONS

    # Execute a tool_use block:
    result = await dispatch(tool_name, tool_input, user_id)
"""

from app.tools import (
    check_scope,
    get_user_context,
    lookup_procedure,
    recall_memory,
    retrieve_knowledge,
    save_memory,
)
from app.tools._types import ToolResult

_REGISTRY: dict = {
    "retrieve_knowledge": retrieve_knowledge,
    "get_user_context": get_user_context,
    "recall_memory": recall_memory,
    "lookup_procedure": lookup_procedure,
    "save_memory": save_memory,
    "check_scope": check_scope,
}

TOOL_DEFINITIONS: list[dict] = [mod.DEFINITION for mod in _REGISTRY.values()]


async def dispatch(name: str, inputs: dict, user_id: str) -> ToolResult:
    """Run a tool by name. Returns ToolResult with error set on unknown tool."""
    module = _REGISTRY.get(name)
    if module is None:
        return ToolResult(content={}, error=f"Unknown tool: {name!r}")
    return await module.run(inputs, user_id)


__all__ = ["TOOL_DEFINITIONS", "ToolResult", "dispatch"]
