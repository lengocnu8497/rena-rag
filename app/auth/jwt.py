import asyncio
import time

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

# ---------------------------------------------------------------------------
# JWKS cache — fetched once, refreshed every hour
# ---------------------------------------------------------------------------

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_lock = asyncio.Lock()
_JWKS_TTL = 3600  # seconds


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    async with _jwks_lock:
        if _jwks_cache and (time.monotonic() - _jwks_fetched_at) < _JWKS_TTL:
            return _jwks_cache
        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = time.monotonic()
        return _jwks_cache


# ---------------------------------------------------------------------------
# Core verification — returns user_id (UUID string from sub claim)
# ---------------------------------------------------------------------------

async def verify_supabase_jwt(token: str) -> str:
    jwks = await _get_jwks()
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise ValueError(f"Invalid JWT: {exc}") from exc

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise ValueError("JWT missing sub claim")
    return user_id


# ---------------------------------------------------------------------------
# FastAPI dependency — extracts Bearer token and resolves to user_id
# ---------------------------------------------------------------------------

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    try:
        return await verify_supabase_jwt(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
