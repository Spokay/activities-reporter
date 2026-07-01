import asyncio
import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from config import get_settings

_bearer = HTTPBearer(auto_error=False)
_JWKS_TTL: int = 3600


class _JwksCache:
    def __init__(self) -> None:
        self._data: dict[str, Any] | None = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return self._data is not None and time.monotonic() - self._fetched_at < _JWKS_TTL

    async def get(self, force: bool = False) -> dict[str, Any]:
        if not force and self._is_fresh():
            assert self._data is not None
            return self._data
        async with self._lock:
            if not force and self._is_fresh():
                assert self._data is not None
                return self._data
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        f"{get_settings().oauth_issuer}/protocol/openid-connect/certs"
                    )
                    r.raise_for_status()
                    jwks: dict[str, Any] = r.json()
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Auth service unreachable",
                ) from exc
            self._data = jwks
            self._fetched_at = time.monotonic()
            return jwks


_jwks_cache = _JwksCache()


async def verify_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    for force in (False, True):
        try:
            return jwt.decode(
                token,
                await _jwks_cache.get(force=force),
                algorithms=["RS256"],
                audience=settings.oauth_audience or settings.oauth_client_id,
                issuer=settings.oauth_issuer,
                options={"verify_at_hash": False},
            )
        except JWTError:
            pass
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.oauth_issuer:
        return None
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await verify_token(credentials.credentials)