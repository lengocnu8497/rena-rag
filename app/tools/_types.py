from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    content: dict[str, Any]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_text(self) -> str:
        """Serialise for the Anthropic tool_result content block."""
        import json
        if self.error:
            return json.dumps({"error": self.error})
        return json.dumps(self.content)
