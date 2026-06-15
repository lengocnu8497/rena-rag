"""
Request logging middleware.

Assigns a UUID request_id to every request, logs it on completion with
method, path, status, and latency. Sets X-Request-Id response header.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("rena.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        t_start = time.monotonic()

        response: Response = await call_next(request)

        latency_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "%s %s %d",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )

        response.headers["X-Request-Id"] = request_id
        return response
