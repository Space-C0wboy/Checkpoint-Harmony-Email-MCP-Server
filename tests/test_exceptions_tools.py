import httpx
import respx

from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.tools import exceptions

AUTH_URL = "https://gw.example/auth/external"
API_URL = "https://gw.example/app/hec-api"


def _settings():
    return Settings(
        checkpoint_client_id="cid", checkpoint_secret="sec",
        checkpoint_auth_url=AUTH_URL, checkpoint_api_url=API_URL, checkpoint_scope="s1",
    )


def _auth():
    respx.post(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "tok"}})
    )


@respx.mock
async def test_list():
    _auth()
    respx.get(f"{API_URL}/v1.0/exceptions/Whitelist").mock(
        return_value=httpx.Response(200, json={"responseData": []})
    )
    out = await exceptions.exceptions_list(_settings(), exc_type="Whitelist")
    assert out == {"responseData": []}


@respx.mock
async def test_get():
    _auth()
    respx.get(f"{API_URL}/v1.0/exceptions/Whitelist/X1").mock(
        return_value=httpx.Response(200, json={"responseData": [{"id": "X1"}]})
    )
    out = await exceptions.exceptions_get(_settings(), exc_type="Whitelist", exc_id="X1")
    assert out["responseData"][0]["id"] == "X1"


@respx.mock
async def test_create():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/exceptions/Whitelist").mock(
        return_value=httpx.Response(200, json={"responseEnvelope": {"responseCode": 0}})
    )
    out = await exceptions.exceptions_create(
        _settings(), exc_type="Whitelist", fields={"senderEmail": "a@b.com", "comment": "trusted"}
    )
    assert out["responseEnvelope"]["responseCode"] == 0
    body = route.calls.last.request.read()
    assert b"requestData" in body and b"senderEmail" in body


@respx.mock
async def test_update():
    _auth()
    route = respx.put(f"{API_URL}/v1.0/exceptions/Whitelist/X1").mock(
        return_value=httpx.Response(200, json={"responseEnvelope": {"responseCode": 0}})
    )
    out = await exceptions.exceptions_update(
        _settings(), exc_type="Whitelist", exc_id="X1", fields={"comment": "updated"}
    )
    assert out["responseEnvelope"]["responseCode"] == 0
    assert b"requestData" in route.calls.last.request.read()


@respx.mock
async def test_delete():
    _auth()
    respx.post(f"{API_URL}/v1.0/exceptions/Whitelist/delete/X1").mock(
        return_value=httpx.Response(200, json={"responseEnvelope": {"responseCode": 0}})
    )
    out = await exceptions.exceptions_delete(_settings(), exc_type="Whitelist", exc_id="X1")
    assert out["responseEnvelope"]["responseCode"] == 0
