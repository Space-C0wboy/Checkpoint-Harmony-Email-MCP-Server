import asyncio
import logging
import uuid
from typing import Any

import httpx

from .auth import TokenManager
from .config import Settings
from .errors import ApiError, RateLimitError

logger = logging.getLogger("checkpoint_harmony_mcp.client")

# Number of automatic retries on HTTP 429 before giving up.
_MAX_429_RETRIES = 2


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

    async def __aenter__(self) -> "HarmonyClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def post(
        self, path: str, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._request("POST", path, json=json, params=params)

    async def put(
        self, path: str, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._request("PUT", path, json=json, params=params)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("DELETE", path, params=params)

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "x-av-req-id": str(uuid.uuid4()),
            "scopes": self._settings.checkpoint_scope,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempted_refresh = False
        for attempt in range(_MAX_429_RETRIES + 1):
            token = await self._auth.get_token()
            resp = await self._http.request(
                method,
                path,
                params=params,
                json=json,
                headers=self._headers(token),
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
