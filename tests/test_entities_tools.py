import httpx
import pytest
import respx

from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.errors import HarmonyError
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
        _settings(), entity_ids=["ENT1"], entity_type="office365_emails_email",
        entity_action_name="quarantine", entity_action_param="malicious", wait=False,
    )
    assert out["responseData"][0]["taskId"] == 3
    body = route.calls.last.request.read()
    assert b"entityIds" in body


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


@respx.mock
async def test_entities_query_max_records_paginates():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(side_effect=[
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 3, "scrollId": "S1"}, "responseData": [_entity("E1"), _entity("E2")]}),
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 3, "scrollId": "S2"}, "responseData": [_entity("E3")]}),
    ])
    out = await entities.entities_query(_settings(), entity_filter={"saas": "office365_emails", "startDate": "x"}, max_records=10)
    assert len(out["responseData"]) == 3
    assert "entitySecurityResult" not in out["responseData"][0]


@respx.mock
async def test_entities_query_count_only():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 12},
        "responseData": [_entity("E1"), {**_entity("E2"), "entitySecurityResult": {"combinedVerdict": {"ap": "clean"}}}]}))
    out = await entities.entities_query(_settings(), entity_filter={"saas": "x", "startDate": "y"}, count_only=True)
    assert out["recordsNumber"] == 12
    assert out["histogram"]["phishing"] == 1 and out["histogram"]["clean"] == 1
    assert "responseData" not in out


@respx.mock
async def test_entities_find_server_side_exact():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/search/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 1, "scrollId": ""}, "responseData": [_entity("E1")]}))
    out = await entities.entities_find(_settings(), sender="a@b.com", start_date="2026-06-01T00:00:00Z")
    assert out["matchMode"] == "exact"
    assert len(out["matches"]) == 1 and out["matches"][0]["entityId"] == "E1"
    import json as _json
    ef = _json.loads(route.calls.last.request.read())["requestData"]["entityExtendedFilter"]
    assert {"saasAttrName": "entityPayload.fromEmail", "saasAttrOp": "is", "saasAttrValue": "a@b.com"} in ef


@respx.mock
async def test_entities_find_falls_back_to_contains():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(side_effect=[
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 0, "scrollId": ""}, "responseData": []}),
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 1, "scrollId": ""}, "responseData": [_entity("E1")]}),
    ])
    out = await entities.entities_find(_settings(), sender="proton.me", start_date="2026-06-01T00:00:00Z")
    assert out["matchMode"] == "contains"
    assert len(out["matches"]) == 1


@respx.mock
async def test_entities_find_subject_uses_contains():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/search/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 1, "scrollId": ""}, "responseData": [_entity("E1")]}))
    out = await entities.entities_find(_settings(), subject_contains="imaging", start_date="2026-06-01T00:00:00Z")
    import json as _json
    ef = _json.loads(route.calls.last.request.read())["requestData"]["entityExtendedFilter"]
    assert ef[0] == {"saasAttrName": "entityPayload.subject", "saasAttrOp": "contains", "saasAttrValue": "imaging"}
    assert out["matchMode"] == "contains"


@respx.mock
async def test_entities_find_defaults_window_when_no_start_date():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/search/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 0, "scrollId": ""}, "responseData": []}))
    await entities.entities_find(_settings(), sender="a@b.com")
    import json as _json
    ef = _json.loads(route.calls.last.request.read())["requestData"]["entityFilter"]
    assert ef.get("startDate")
    assert "endDate" not in ef


@respx.mock
async def test_entities_find_entity_id_short_circuits():
    _auth()
    g = respx.get(f"{API_URL}/v1.0/search/entity/ENT1").mock(return_value=httpx.Response(200, json={
        "responseData": [_entity("ENT1")]}))
    q = respx.post(f"{API_URL}/v1.0/search/query").mock(return_value=httpx.Response(200, json={"responseData": []}))
    out = await entities.entities_find(_settings(), entity_id="ENT1")
    assert g.called and not q.called
    assert out["matches"][0]["entityId"] == "ENT1" and out["matchMode"] == "exact"


@respx.mock
async def test_entities_find_truncated_when_more_than_limit():
    _auth()
    respx.post(f"{API_URL}/v1.0/search/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 50, "scrollId": ""}, "responseData": [_entity("E1")]}))
    out = await entities.entities_find(_settings(), sender="a@b.com", start_date="x", limit=1)
    assert out["truncated"] is True and out["totalInWindow"] == 50


@respx.mock
async def test_entities_find_requires_filter():
    with pytest.raises(HarmonyError):
        await entities.entities_find(_settings(), start_date="2026-06-01T00:00:00Z")


@respx.mock
async def test_entities_action_wait_returns_final_state():
    _auth()
    respx.post(f"{API_URL}/v1.0/action/entity").mock(return_value=httpx.Response(
        200, json={"responseData": [{"entityId": "ENT1", "taskId": "T3"}]}))
    respx.get(f"{API_URL}/v1.0/task/T3").mock(return_value=httpx.Response(
        200, json={"responseData": {"actions": [{"action_status": "completed"}]}}))
    respx.get(f"{API_URL}/v1.0/search/entity/ENT1").mock(return_value=httpx.Response(
        200, json={"responseData": [{"entityInfo": {"entityId": "ENT1", "entityActionState": "quarantined"}, "entityPayload": {"isQuarantined": True, "isRestored": False}}]}))
    out = await entities.entities_action(_settings(), entity_ids=["ENT1"], entity_type="office365_emails_email", entity_action_name="quarantine", timeout=0)
    assert out["status"] == "completed" and out["taskId"] == "T3"
    assert out["finalState"]["isQuarantined"] is True


@respx.mock
async def test_entities_action_body_uses_scalars_and_entity_type():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/action/entity").mock(
        return_value=httpx.Response(200, json={"responseData": [{"entityId": "ENT1", "taskId": "T3"}]}))
    await entities.entities_action(
        _settings(), entity_ids=["ENT1"], entity_type="office365_emails_email",
        entity_action_name="quarantine", entity_action_param="malicious", wait=False,
    )
    import json as _json
    body = _json.loads(route.calls.last.request.read())
    rd = body["requestData"]
    assert rd["entityIds"] == ["ENT1"]
    assert rd["entityType"] == "office365_emails_email"   # required, present
    assert rd["entityActionName"] == "quarantine"          # scalar
    assert rd["entityActionParam"] == "malicious"          # scalar
    assert "scope" not in rd


@respx.mock
async def test_entities_action_bulk_returns_summary():
    _auth()
    respx.post(f"{API_URL}/v1.0/action/entity").mock(return_value=httpx.Response(200, json={
        "responseData": [{"entityId": "ENT1", "taskId": "T1"}, {"entityId": "ENT2", "taskId": "T2"}]}))
    for tid in ("T1", "T2"):
        respx.get(f"{API_URL}/v1.0/task/{tid}").mock(return_value=httpx.Response(
            200, json={"responseData": {"actions": [{"action_status": "completed"}]}}))
    for eid in ("ENT1", "ENT2"):
        respx.get(f"{API_URL}/v1.0/search/entity/{eid}").mock(return_value=httpx.Response(
            200, json={"responseData": [{"entityInfo": {"entityId": eid, "entityActionState": "quarantined"},
                                          "entityPayload": {"isQuarantined": True}}]}))
    out = await entities.entities_action(
        _settings(), entity_ids=["ENT1", "ENT2"], entity_type="office365_emails_email", entity_action_name="quarantine", timeout=0,
    )
    assert out["summary"]["completed"] == 2


@respx.mock
async def test_entities_download_returns_filename_and_base64():
    _auth()
    respx.get(f"{API_URL}/v1.0/download/entity/ENT1").mock(return_value=httpx.Response(
        200, content=b"From: a@b\r\n\r\nhi",
        headers={
            "Content-Type": "application/message/rfc822",
            "Content-Disposition": 'attachment; filename="ENT1.eml"',
        },
    ))
    out = await entities.entities_download(_settings(), entity_id="ENT1")
    assert out["filename"] == "ENT1.eml"
    assert out["contentType"] == "application/message/rfc822"
    assert out["sizeBytes"] == len(b"From: a@b\r\n\r\nhi")
    import base64
    assert base64.b64decode(out["base64"]) == b"From: a@b\r\n\r\nhi"


@respx.mock
async def test_entities_download_404_raises():
    _auth()
    respx.get(f"{API_URL}/v1.0/download/entity/missing").mock(return_value=httpx.Response(404, text="nope"))
    from checkpoint_harmony_mcp.errors import HarmonyError, ApiError
    with pytest.raises((HarmonyError, ApiError)):
        await entities.entities_download(_settings(), entity_id="missing")


@respx.mock
async def test_entities_query_extended_filter_accepts_json_string():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/search/query").mock(
        return_value=httpx.Response(200, json={"responseData": []}))
    import json as _json
    await entities.entities_query(
        _settings(), entity_filter={"saas": "office365_emails", "startDate": "x"},
        extended_filter=_json.dumps([
            {"saasAttrName": "entityPayload.fromEmail", "saasAttrOp": "is", "saasAttrValue": "a@b.com"}
        ]),
    )
    body = _json.loads(route.calls.last.request.read())
    ef = body["requestData"]["entityExtendedFilter"]
    assert ef[0]["saasAttrName"] == "entityPayload.fromEmail"
    assert ef[0]["saasAttrOp"] == "is"
    assert ef[0]["saasAttrValue"] == "a@b.com"


async def test_entities_query_extended_filter_rejects_bad_json_string():
    with pytest.raises(HarmonyError, match="JSON array"):
        await entities.entities_query(
            _settings(), entity_filter={"saas": "office365_emails", "startDate": "x"},
            extended_filter="not json",
        )


async def test_entities_query_extended_filter_rejects_non_list():
    with pytest.raises(HarmonyError, match="list of"):
        await entities.entities_query(
            _settings(), entity_filter={"saas": "office365_emails", "startDate": "x"},
            extended_filter='{"saasAttrName": "x"}',  # JSON object, not an array
        )
