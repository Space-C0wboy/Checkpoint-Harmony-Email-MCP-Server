import httpx
import pytest
import respx

from checkpoint_harmony_mcp.client import HarmonyClient
from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.errors import ApiError, RateLimitError

AUTH_URL = "https://gw.example/auth/external"
API_URL = "https://gw.example/app/hec-api"


def _settings(**over):
    base = dict(
        checkpoint_client_id="cid",
        checkpoint_secret="sec",
        checkpoint_auth_url=AUTH_URL,
        checkpoint_api_url=API_URL,
        checkpoint_scope="scope-1",
    )
    base.update(over)
    return Settings(**base)


def _auth_route():
    return respx.post(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "tok"}})
    )


@respx.mock
async def test_get_returns_json_and_sends_required_headers():
    _auth_route()
    route = respx.get(f"{API_URL}/v1.0/event/E1").mock(
        return_value=httpx.Response(200, json={"responseData": [{"eventId": "E1"}]})
    )
    async with HarmonyClient(_settings()) as client:
        body = await client.get("/v1.0/event/E1")
    assert body["responseData"][0]["eventId"] == "E1"
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer tok"
    assert sent.headers["scopes"] == "scope-1"
    assert "x-av-req-id" in sent.headers


@respx.mock
async def test_post_sends_json_body():
    _auth_route()
    route = respx.post(f"{API_URL}/v1.0/action/event").mock(
        return_value=httpx.Response(200, json={"responseData": []})
    )
    async with HarmonyClient(_settings()) as client:
        await client.post("/v1.0/action/event", json={"requestData": {"eventIds": ["E1"]}})
    assert b"requestData" in route.calls.last.request.read()


@respx.mock
async def test_put_and_delete_methods_exist():
    _auth_route()
    respx.put(f"{API_URL}/v1.0/exceptions/Whitelist/X1").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    respx.post(f"{API_URL}/v1.0/exceptions/Whitelist/delete/X1").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    async with HarmonyClient(_settings()) as client:
        assert (await client.put("/v1.0/exceptions/Whitelist/X1", json={"requestData": {}}))["ok"]
        assert (await client.post("/v1.0/exceptions/Whitelist/delete/X1"))["ok"]


@respx.mock
async def test_delete_sends_json_body():
    _auth_route()
    route = respx.delete(f"{API_URL}/v1.0/sectool-exceptions/avanan_url/exceptions").mock(
        return_value=httpx.Response(204)
    )
    async with HarmonyClient(_settings()) as client:
        out = await client.delete(
            "/v1.0/sectool-exceptions/avanan_url/exceptions",
            json={"requestData": {"exception_type": "block-domain", "exception_str_list": ["evil.example"]}},
        )
    assert out == {}  # 204 -> empty body -> {}
    import json as _json
    body = _json.loads(route.calls.last.request.read())
    assert body["requestData"]["exception_str_list"] == ["evil.example"]


@respx.mock
async def test_401_triggers_refresh_and_retry():
    auth = respx.post(AUTH_URL).mock(
        side_effect=[
            httpx.Response(200, json={"success": True, "data": {"token": "old"}}),
            httpx.Response(200, json={"success": True, "data": {"token": "new"}}),
        ]
    )
    respx.get(f"{API_URL}/v1.0/event/E1").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"responseData": []})]
    )
    async with HarmonyClient(_settings()) as client:
        body = await client.get("/v1.0/event/E1")
    assert body == {"responseData": []}
    assert auth.call_count == 2


@respx.mock
async def test_429_raises_rate_limit_error():
    _auth_route()
    respx.get(f"{API_URL}/v1.0/event/E1").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"})
    )
    async with HarmonyClient(_settings()) as client:
        with pytest.raises(RateLimitError):
            await client.get("/v1.0/event/E1")


@respx.mock
async def test_500_raises_api_error():
    _auth_route()
    respx.get(f"{API_URL}/v1.0/event/E1").mock(return_value=httpx.Response(500, text="server error"))
    async with HarmonyClient(_settings()) as client:
        with pytest.raises(ApiError) as exc:
            await client.get("/v1.0/event/E1")
    assert exc.value.status_code == 500


@respx.mock
async def test_get_bytes_returns_raw_bytes_and_headers():
    _auth_route()
    respx.get(f"{API_URL}/v1.0/download/entity/E1").mock(return_value=httpx.Response(
        200,
        content=b"From: x@y\r\nSubject: hi\r\n\r\nhello",
        headers={
            "Content-Type": "application/message/rfc822",
            "Content-Disposition": "attachment; filename=E1.eml",
        },
    ))
    async with HarmonyClient(_settings()) as c:
        body, headers = await c.get_bytes("/v1.0/download/entity/E1")
    assert body.startswith(b"From: x@y")
    assert headers.get("Content-Type") == "application/message/rfc822"


@respx.mock
async def test_get_bytes_404_raises_apierror():
    _auth_route()
    respx.get(f"{API_URL}/v1.0/download/entity/missing").mock(return_value=httpx.Response(404, text="not found"))
    async with HarmonyClient(_settings()) as c:
        with pytest.raises(ApiError) as exc:
            await c.get_bytes("/v1.0/download/entity/missing")
    assert exc.value.status_code == 404


@respx.mock
async def test_request_honors_named_bucket_throttle():
    _auth_route()
    respx.post(f"{API_URL}/v1.0/event/query").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with HarmonyClient(_settings()) as c:
        c.set_bucket("test_bucket", rate_per_sec=2.0, burst=1)
        import time as _t
        start = _t.monotonic()
        await c.post("/v1.0/event/query", json={"requestData": {}}, bucket="test_bucket")
        await c.post("/v1.0/event/query", json={"requestData": {}}, bucket="test_bucket")
        elapsed = _t.monotonic() - start
    assert elapsed >= 0.4, f"expected throttling, took only {elapsed:.2f}s"
