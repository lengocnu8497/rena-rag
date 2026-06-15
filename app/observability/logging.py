"""
Structured JSON logging for the rena-rag service.

Call configure_logging() once at startup (main.py lifespan).
All app loggers then emit JSON lines readable by CloudWatch Logs Insights.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_SKIP = frozenset(
    [
        "args", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message",
        "msg", "name", "pathname", "process", "processName", "relativeCreated",
        "stack_info", "taskName", "thread", "threadName",
    ]
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info)

        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Extra fields added via logger.info("msg", extra={...})
        for key, val in record.__dict__.items():
            if key not in _SKIP and not key.startswith("_"):
                payload[key] = val

        if record.exc_text:
            payload["exception"] = record.exc_text

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "supabase", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
