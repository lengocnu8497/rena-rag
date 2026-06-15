"""
Metric helpers for the eval harness.
"""

from __future__ import annotations

import statistics
from typing import Any


def mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def percentile(values: list[float], p: int) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * p / 100) - 1)
    return sorted_vals[idx]


def pass_rate(results: list[bool]) -> float:
    return round(sum(results) / len(results), 4) if results else 0.0


def format_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))

    header = "  ".join(col.ljust(widths[col]) for col in columns)
    sep = "  ".join("-" * widths[col] for col in columns)
    lines = [header, sep]
    for row in rows:
        lines.append("  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns))
    return "\n".join(lines)
