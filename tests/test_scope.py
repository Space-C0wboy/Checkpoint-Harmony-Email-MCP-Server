import httpx
import pytest
import respx

from checkpoint_harmony_mcp.client import HarmonyClient
from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.errors import HarmonyError

AUTH = "https://gw.example/auth/external"
API = "https://gw.example/app/hec-api"


def _settings(scope=""):
    return Settings(
        checkpoint_client_id="c", checkpoint_secret="s",
        checkpoint_auth_url=AUTH, checkpoint_api_url=API, checkpoint_scope=scope,
    )


def _auth():
    respx.post(AUTH).mock(return_value=httpx.Response(200, json={"success": True, "data": {"token": "t"}}))


@respx.mock
async def test_explicit_scope_used_no_discovery():
    _auth()
    scopes_route = respx.get(f"{API}/v1.0/scopes").mock(return_value=httpx.Response(200, json={"responseData": ["X"]}))
    route = respx.get(f"{API}/v1.0/event/E1").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with HarmonyClient(_settings(scope="explicit")) as c:
        await c.get("/v1.0/event/E1")
    assert route.calls.last.request.headers["scopes"] == "explicit"
    assert scopes_route.call_count == 0


@respx.mock
async def test_single_scope_auto_discovered_and_cached():
    _auth()
    scopes_route = respx.get(f"{API}/v1.0/scopes").mock(return_value=httpx.Response(200, json={"responseData": ["auto-1"]}))
    ev = respx.get(f"{API}/v1.0/event/E1").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with HarmonyClient(_settings()) as c:
        await c.get("/v1.0/event/E1")
        await c.get("/v1.0/event/E1")
    assert ev.calls.last.request.headers["scopes"] == "auto-1"
    assert scopes_route.call_count == 1


@respx.mock
async def test_scopes_endpoint_does_not_recurse():
    _auth()
    scopes_route = respx.get(f"{API}/v1.0/scopes").mock(return_value=httpx.Response(200, json={"responseData": ["a", "b"]}))
    async with HarmonyClient(_settings()) as c:
        out = await c.get("/v1.0/scopes")
    assert out["responseData"] == ["a", "b"]
    assert scopes_route.call_count == 1
    assert scopes_route.calls.last.request.headers["scopes"] == ""


@respx.mock
async def test_multiple_scopes_joined_as_csv():
    _auth()
    scopes_route = respx.get(f"{API}/v1.0/scopes").mock(
        return_value=httpx.Response(200, json={"responseData": ["alpha", "beta"]}))
    ev = respx.get(f"{API}/v1.0/event/E1").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with HarmonyClient(_settings()) as c:
        await c.get("/v1.0/event/E1")
    assert ev.calls.last.request.headers["scopes"] == "alpha,beta"
    assert scopes_route.call_count == 1


@respx.mock
async def test_zero_scopes_still_raises():
    _auth()
    respx.get(f"{API}/v1.0/scopes").mock(return_value=httpx.Response(200, json={"responseData": []}))
    async with HarmonyClient(_settings()) as c:
        with pytest.raises(HarmonyError):
            await c.get("/v1.0/event/E1")
