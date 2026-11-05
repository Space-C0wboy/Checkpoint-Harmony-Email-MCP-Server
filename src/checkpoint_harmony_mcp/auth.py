import asyncio
import time

import httpx

from .config import Settings
from .errors import AuthError

# Default token lifetime when the auth response omits expiry info.
_DEFAULT_EXPIRES_IN = 3600
# Refresh this many seconds before expiry to avoid edge-of-expiry 401s.
_EXPIRY_SKEW = 60


class TokenManager:
    """Fetches and caches a Harmony API bearer token using client credentials."""

    def __init__(self, settings: Settings, http: httpx.AsyncClient):
        self._settings = settings
        self._http = http
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and time.monotonic() < self._expires_at:
            return self._token
        async with self._lock:
            # Re-check inside the lock: another coroutine may have refreshed.
            if not force_refresh and self._token and time.monotonic() < self._expires_at:
                return self._token
            return await self._refresh()

    async def _refresh(self) -> str:
        try:
            resp = await self._http.post(
                self._settings.checkpoint_auth_url,
                json={
                    "clientId": self._settings.checkpoint_client_id,
                    "accessKey": self._settings.checkpoint_secret.get_secret_value(),
                },
                timeout=self._settings.checkpoint_timeout,
            )
        except httpx.HTTPError as exc:
            raise AuthError(f"Auth request failed: {exc}") from exc

        if resp.status_code != 200:
            raise AuthError(f"Auth failed with status {resp.status_code}")

        data = (resp.json() or {}).get("data") or {}
        token = data.get("token")
        if not token:
            raise AuthError("Auth response did not contain a token")

        # Token TTL: prefer the documented `expiresIn` (seconds). Fall back to
        # parsing `expires` (ISO 8601). If both are absent, default to 3600s.
        # See Check Point Email Security API Reference Guide p. 7 (defers to the
        # Portal Administration Guide for the auth response shape).
        ttl = data.get("expiresIn")
        if ttl is None and isinstance(data.get("expires"), str):
            try:
                from datetime import datetime, timezone
                exp_iso = data["expires"].replace("Z", "+00:00")
                ttl = int((datetime.fromisoformat(exp_iso) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError):  # bad ISO string, or a naive timestamp vs aware now
                ttl = None
        try:
            ttl = int(ttl) if ttl is not None else _DEFAULT_EXPIRES_IN
        except (TypeError, ValueError):
            ttl = _DEFAULT_EXPIRES_IN
        self._token = token
        self._expires_at = time.monotonic() + max(ttl - _EXPIRY_SKEW, 0)
        return token
