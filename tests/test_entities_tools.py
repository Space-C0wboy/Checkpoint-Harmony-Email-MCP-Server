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


def _entity(eid):
    return {
        "saasInfo": {"saasActorPayload": {"full_name": "HEAVY"}},
        "entityInfo": {
            "entityId": eid, "saas": "office365_emails",
            "saasEntityType": "office365_emails_email", "entityActionState": "quarantined",
        },
        "entityPayload": {
            "subject": "Imaging Import Status", "fromEmail": "a@b.com",
            "fromDomain": "b.com", "recipients": ["c@d.com"],
            "received": "2026-05-27T23:59:50Z", "isQuarantined": True,
            "SpfResult": "fail", "size": 16037, "attachments": ["HEAVY"],
        },
        "entitySecurityResult": {
            "combinedVerdict": {"ap": "phishing"},
            "ap": [{"payload": {"reasons": ["HEAVY-LIST"]}}],
        },
        "entityActions": [{"x": 1}], "entityAvailableActions": [],
    }


@respx.mock
async def test_query_compacts_by_default():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(
        return_value=httpx.Response(200, json={
            "responseEnvelope": {"recordsNumber": 2, "scrollId": "S1"},
            "responseData": [_entity("ENT1"), _entity("ENT2")],
        })
    )
    out = await entities.entities_query(
        _settings(), entity_filter={"saas": "office365_emails", "startDate": "x"}
    )
    rec = out["responseData"][0]
    assert rec["entityId"] == "ENT1"
    assert rec["saasEntityType"] == "office365_emails_email"
    assert rec["subject"] == "Imaging Import Status"
    assert rec["combinedVerdict"] == {"ap": "phishing"}
    assert "entitySecurityResult" not in rec and "ap" not in rec
    assert "saasInfo" not in rec
    assert out["responseEnvelope"]["scrollId"] == "S1"


@respx.mock
async def test_query_limit_truncates():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(
        return_value=httpx.Response(200, json={
            "responseData": [_entity("E1"), _entity("E2"), _entity("E3")]
        })
    )
    out = await entities.entities_query(
        _settings(), entity_filter={"saas": "x", "startDate": "y"}, limit=1
    )
    assert len(out["responseData"]) == 1


@respx.mock
async def test_query_full_returns_verbatim():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(
        return_value=httpx.Response(200, json={"responseData": [_entity("E1")]})
    )
    out = await entities.entities_query(
        _settings(), entity_filter={"saas": "x", "startDate": "y"}, full=True
    )
    assert out["responseData"][0]["entitySecurityResult"]["ap"][0]["payload"]["reasons"] == ["HEAVY-LIST"]
