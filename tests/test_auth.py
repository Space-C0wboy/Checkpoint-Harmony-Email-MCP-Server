import httpx
import pytest
import respx

from checkpoint_harmony_mcp.auth import TokenManager
from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.errors import AuthError

AUTH_URL = "https://gw.example/auth/external"


def _settings():
    return Settings(
        checkpoint_client_id="cid",
        checkpoint_secret="sec",
        checkpoint_auth_url=AUTH_URL,
        checkpoint_api_url="https://gw.example/app/hec-api",
    )


@respx.mock
async def test_fetches_and_caches_token():
    route = respx.post(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "abc"}})
    )
    async with httpx.AsyncClient() as http:
        tm = TokenManager(_settings(), http)
        assert await tm.get_token() == "abc"
        assert await tm.get_token() == "abc"
    assert route.call_count == 1


@respx.mock
async def test_sends_client_credentials():
    route = respx.post(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "abc"}})
    )
    async with httpx.AsyncClient() as http:
        await TokenManager(_settings(), http).get_token()
    body = route.calls.last.request.read()
    assert b"clientId" in body and b"accessKey" in body


@respx.mock
async def test_refresh_forces_new_token():
    respx.post(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "t2"}})
    )
    async with httpx.AsyncClient() as http:
        tm = TokenManager(_settings(), http)
        await tm.get_token()
        assert await tm.get_token(force_refresh=True) == "t2"


@respx.mock
async def test_auth_failure_raises():
    respx.post(AUTH_URL).mock(return_value=httpx.Response(401, json={"success": False}))
    async with httpx.AsyncClient() as http:
        tm = TokenManager(_settings(), http)
        with pytest.raises(AuthError):
            await tm.get_token()


@respx.mock
async def test_missing_token_raises():
    respx.post(AUTH_URL).mock(return_value=httpx.Response(200, json={"success": True, "data": {}}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(AuthError):
            await TokenManager(_settings(), http).get_token()


@respx.mock
async def test_uses_expires_iso_when_no_expiresin():
    from datetime import datetime, timedelta, timezone
    iso = (datetime.now(timezone.utc) + timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    respx.post(AUTH_URL).mock(return_value=httpx.Response(
        200, json={"success": True, "data": {"token": "abc", "expires": iso}}))
    async with httpx.AsyncClient() as http:
        tm = TokenManager(_settings(), http)
        assert await tm.get_token() == "abc"
        assert await tm.get_token() == "abc"  # cached


@respx.mock
async def test_naive_expires_falls_back_to_default_ttl():
    # no timezone -> naive datetime; subtracting it from an aware now raises TypeError, which must not escape
    respx.post(AUTH_URL).mock(return_value=httpx.Response(
        200, json={"success": True, "data": {"token": "abc", "expires": "2099-01-01T00:00:00"}}))
    async with httpx.AsyncClient() as http:
        assert await TokenManager(_settings(), http).get_token() == "abc"


@respx.mock
async def test_default_ttl_when_no_expiry_fields():
    respx.post(AUTH_URL).mock(return_value=httpx.Response(
        200, json={"success": True, "data": {"token": "abc"}}))
    async with httpx.AsyncClient() as http:
        tm = TokenManager(_settings(), http)
        assert await tm.get_token() == "abc"
        assert await tm.get_token() == "abc"
