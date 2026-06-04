import httpx
import respx

from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.tools import entities

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
async def test_get_by_id():
    _auth()
    respx.get(f"{API_URL}/v1.0/search/entity/ENT1").mock(
        return_value=httpx.Response(200, json={"responseData": [{"entityInfo": {"entityId": "ENT1"}}]})
    )
    out = await entities.entities_get_by_id(_settings(), entity_id="ENT1")
    assert out["responseData"][0]["entityInfo"]["entityId"] == "ENT1"


@respx.mock
async def test_query():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/search/query").mock(
        return_value=httpx.Response(200, json={"responseData": []})
    )
    out = await entities.entities_query(_settings(), entity_filter={"saas": "office365_emails"})
    assert out == {"responseData": []}
    body = route.calls.last.request.read()
    assert b"requestData" in body and b"entityFilter" in body


@respx.mock
async def test_action():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/action/entity").mock(
        return_value=httpx.Response(200, json={"responseData": [{"taskId": 3}]})
    )
    out = await entities.entities_action(
        _settings(), entity_ids=["ENT1"], entity_type="office365_emails",
        entity_action_name="quarantine", entity_action_param="malicious",
    )
    assert out["responseData"][0]["taskId"] == 3
    body = route.calls.last.request.read()
    assert b"entityIds" in body and b"entityType" in body
