import httpx
import pytest
import respx

from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.errors import HarmonyError
from checkpoint_harmony_mcp.tools import sectool_exceptions as sx

AUTH_URL = "https://gw.example/auth/external"
API_URL = "https://gw.example/app/hec-api"


def _settings():
    return Settings(
        checkpoint_client_id="cid", checkpoint_secret="sec",
        checkpoint_auth_url=AUTH_URL, checkpoint_api_url=API_URL, checkpoint_scope="s1",
    )


def _auth():
    respx.post(AUTH_URL).mock(return_value=httpx.Response(
        200, json={"success": True, "data": {"token": "tok"}}))


# ---------- URL Reputation ----------

@respx.mock
async def test_urlrep_list():
    _auth()
    respx.get(f"{API_URL}/v1.0/sectool-exceptions/avanan_url/exceptions/block-domain").mock(
        return_value=httpx.Response(200, json={"responseData": []}))
    out = await sx.urlrep_list(_settings(), exception_type="block-domain")
    assert out == {"responseData": []}


@respx.mock
async def test_urlrep_get():
    _auth()
    respx.get(f"{API_URL}/v1.0/sectool-exceptions/avanan_url/exceptions/block-domain/evil.example").mock(
        return_value=httpx.Response(200, json={"responseData": [{"exception_str": "evil.example"}]}))
    out = await sx.urlrep_get(_settings(), exception_type="block-domain", exception_str="evil.example")
    assert out["responseData"][0]["exception_str"] == "evil.example"


@respx.mock
async def test_urlrep_create():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/sectool-exceptions/avanan_url").mock(
        return_value=httpx.Response(200, json={"responseEnvelope": {"responseCode": 0}}))
    await sx.urlrep_create(_settings(), exception_type="block-domain",
                           fields={"exception_str": "evil.example", "comment": "test"})
    import json as _json
    body = _json.loads(route.calls.last.request.read())
    assert body["requestData"]["exception_type"] == "block-domain"
    assert body["requestData"]["exception_str"] == "evil.example"


@respx.mock
async def test_urlrep_update():
    _auth()
    route = respx.put(f"{API_URL}/v1.0/sectool-exceptions/avanan_url").mock(
        return_value=httpx.Response(200, json={"responseEnvelope": {"responseCode": 0}}))
    await sx.urlrep_update(_settings(), exception_type="block-domain",
                           fields={"exception_str": "evil.example", "comment": "updated"})
    assert route.called


@respx.mock
async def test_urlrep_delete():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/sectool-exceptions/avanan_url/exceptions").mock(
        return_value=httpx.Response(204, json={"responseEnvelope": {"responseCode": 0}}))
    await sx.urlrep_delete(_settings(), exception_type="block-domain", exception_str="evil.example")
    import json as _json
    body = _json.loads(route.calls.last.request.read())
    assert body["requestData"] == {"exception_type": "block-domain", "exception_str": "evil.example"}


async def test_urlrep_invalid_type_raises():
    with pytest.raises(HarmonyError):
        await sx.urlrep_list(_settings(), exception_type="not-a-real-type")


# ---------- DLP ----------

@respx.mock
async def test_dlp_create():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/sectool-exceptions/avanan_dlp").mock(
        return_value=httpx.Response(200, json={"responseEnvelope": {"responseCode": 0}}))
    await sx.dlp_create(_settings(), exception_type="sender_email",
                        fields={"exception_str": "ok@trusted.com", "comment": "exec"})
    assert route.called


async def test_dlp_invalid_type_raises():
    with pytest.raises(HarmonyError):
        await sx.dlp_list(_settings(), exception_type="nope")
