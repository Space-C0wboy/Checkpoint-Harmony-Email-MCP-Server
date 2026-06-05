import asyncio
import logging
import uuid
from typing import Any

import httpx

from .auth import TokenManager
from .config import Settings
from .errors import ApiError, HarmonyError, RateLimitError
from .tools._common import TokenBucket

logger = logging.getLogger("checkpoint_harmony_mcp.client")

# Number of automatic retries on HTTP 429 before giving up.
_MAX_429_RETRIES = 2
_SCOPES_PATH = "/v1.0/scopes"


class HarmonyClient:
    """Async HTTP client for the Harmony Email & Collaboration smart-api.

    Injects the bearer token, the required ``scopes`` header, and a per-request
    ``x-av-req-id``; refreshes the token once on a 401; backs off on 429.
    """

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self._settings = settings
        self._http = http or httpx.AsyncClient(base_url=settings.checkpoint_api_url)
        self._owns_http = http is None
        self._auth = TokenManager(settings, self._http)
        self._scope: str | None = settings.checkpoint_scope or None
        self._buckets: dict[str, TokenBucket] = {}

    async def __aenter__(self) -> "HarmonyClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            await self._http.aclose()

    def set_bucket(self, name: str, rate_per_sec: float, burst: int) -> None:
        """Register/replace a named token bucket. Calls to ``get/post/put/delete``
        that pass ``bucket=name`` will await this bucket before issuing the HTTP request."""
        self._buckets[name] = TokenBucket(rate_per_sec, burst)

    async def get(self, path: str, params: dict[str, Any] | None = None, bucket: str | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params, bucket=bucket)

    async def post(
        self, path: str, json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None, bucket: str | None = None,
    ) -> dict[str, Any]:
        return await self._request("POST", path, json=json, params=params, bucket=bucket)

    async def put(
        self, path: str, json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None, bucket: str | None = None,
    ) -> dict[str, Any]:
        return await self._request("PUT", path, json=json, params=params, bucket=bucket)

    async def delete(self, path: str, params: dict[str, Any] | None = None, bucket: str | None = None) -> dict[str, Any]:
        return await self._request("DELETE", path, params=params, bucket=bucket)

    async def get_bytes(
        self, path: str, params: dict[str, Any] | None = None
    ) -> tuple[bytes, httpx.Headers]:
        """Issue an authenticated GET that returns raw bytes + response headers.
        Used for binary responses like ``GET /v1.0/download/entity/{id}``. The auth/
        scopes/401-refresh/429-backoff path is the same as ``get``."""
        scope = await self._ensure_scope()
        attempted_refresh = False
        for attempt in range(_MAX_429_RETRIES + 1):
            token = await self._auth.get_token()
            resp = await self._http.request(
                "GET", path, params=params,
                headers=self._headers(token, scope),
                timeout=self._settings.checkpoint_timeout,
            )
            logger.info("GET %s -> %s (bytes)", path, resp.status_code)
            if resp.status_code == 401 and not attempted_refresh:
                attempted_refresh = True
                await self._auth.get_token(force_refresh=True)
                continue
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                if attempt < _MAX_429_RETRIES:
                    await asyncio.sleep(retry_after)
                    continue
                raise RateLimitError("Rate limited", status_code=429)
            if resp.status_code >= 400:
                raise ApiError(
                    f"API error {resp.status_code}: {resp.text[:500]}",
                    status_code=resp.status_code,
                )
            return resp.content, resp.headers
        raise ApiError("Request failed after retries")

    def _headers(self, token: str, scope: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "x-av-req-id": str(uuid.uuid4()),
            "scopes": scope,
        }

    async def _ensure_scope(self) -> str:
        if self._scope:
            return self._scope
        self._scope = await self._discover_scope()
        return self._scope

    async def _discover_scope(self) -> str:
        token = await self._auth.get_token()
        resp = await self._http.request(
            "GET", _SCOPES_PATH,
            headers={"Authorization": f"Bearer {token}", "x-av-req-id": str(uuid.uuid4()), "scopes": ""},
            timeout=self._settings.checkpoint_timeout,
        )
        if resp.status_code >= 400:
            raise ApiError(f"Scope discovery failed {resp.status_code}", status_code=resp.status_code)
        data = (resp.json() or {}).get("responseData") or []
        if not data:
            raise HarmonyError("No scopes available for these credentials")
        joined = ",".join(data)
        if len(data) == 1:
            logger.info("Auto-discovered Harmony scope: %s", joined)
        else:
            logger.info("Auto-discovered %d Harmony scopes (joined): %s", len(data), joined)
        return joined

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        bucket: str | None = None,
    ) -> dict[str, Any]:
        if bucket and bucket in self._buckets:
            await self._buckets[bucket].acquire()
        scope = "" if path.rstrip("/") == _SCOPES_PATH else await self._ensure_scope()
        attempted_refresh = False
        for attempt in range(_MAX_429_RETRIES + 1):
            token = await self._auth.get_token()
            resp = await self._http.request(
                method,
                path,
                params=params,
                json=json,
                headers=self._headers(token, scope),
                timeout=self._settings.checkpoint_timeout,
            )
            logger.info("%s %s -> %s", method, path, resp.status_code)

            if resp.status_code == 401 and not attempted_refresh:
                attempted_refresh = True
                await self._auth.get_token(force_refresh=True)
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1"))
                if attempt < _MAX_429_RETRIES:
                    await asyncio.sleep(retry_after)
                    continue
                raise RateLimitError("Rate limited", status_code=429)

            if resp.status_code >= 400:
                raise ApiError(
                    f"API error {resp.status_code}: {resp.text[:500]}",
                    status_code=resp.status_code,
                )

            if not resp.content:
                return {}
            return resp.json()

        raise ApiError("Request failed after retries")
