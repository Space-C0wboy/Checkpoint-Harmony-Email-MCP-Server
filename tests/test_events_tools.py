import httpx
import pytest
import respx

from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.errors import HarmonyError
from checkpoint_harmony_mcp.tools import events

AUTH_URL = "https://gw.example/auth/external"
API_URL = "https://gw.example/app/hec-api"


def _settings():
    return Settings(
        checkpoint_client_id="cid", checkpoint_secret="sec",
        checkpoint_auth_url=AUTH_URL, checkpoint_api_url=API_URL, checkpoint_scope="s1",
    )


def _auth():
    return respx.post(AUTH_URL).mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "tok"}})
    )


@respx.mock
async def test_get_by_id():
    _auth()
    respx.get(f"{API_URL}/v1.0/event/E1").mock(
        return_value=httpx.Response(200, json={"responseData": [{"eventId": "E1"}]})
    )
    out = await events.events_get_by_id(_settings(), event_id="E1")
    assert out["responseData"][0]["eventId"] == "E1"


@respx.mock
async def test_query():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/event/query").mock(
        return_value=httpx.Response(200, json={"responseData": []})
    )
    out = await events.events_query(_settings(), filters={"startDate": "x", "severities": ["Critical"]})
    assert out == {"responseData": []}
    body = route.calls.last.request.read()
    assert b"requestData" in body and b"severities" in body


@respx.mock
async def test_action():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/action/event").mock(
        return_value=httpx.Response(200, json={"responseData": [{"taskId": 7}]})
    )
    out = await events.events_action(
        _settings(), event_ids=["E1"], event_action_name="quarantine", event_action_param="spam", wait=False
    )
    assert out["responseData"][0]["taskId"] == 7
    body = route.calls.last.request.read()
    assert b"eventIds" in body and b"eventActionName" in body


@respx.mock
async def test_get_task_status():
    _auth()
    respx.get(f"{API_URL}/v1.0/task/T9").mock(
        return_value=httpx.Response(200, json={"responseData": {"actions": [{"action_status": "completed"}]}})
    )
    out = await events.events_get_task_status(_settings(), task_id="T9")
    assert out["status"] == "completed"


@respx.mock
async def test_action_includes_scope_in_request_data():
    _auth()
    route = respx.post(f"{API_URL}/v1.0/action/event").mock(
        return_value=httpx.Response(200, json={})
    )
    await events.events_action(
        _settings(), event_ids=["E1"], event_action_name="quarantine", scope="sc1"
    )
    assert b"scope" in route.calls.last.request.read()


@respx.mock
async def test_shared_client_authenticates_once_across_calls():
    from checkpoint_harmony_mcp.client import HarmonyClient
    auth = _auth()
    respx.get(f"{API_URL}/v1.0/event/E1").mock(return_value=httpx.Response(200, json={}))
    respx.get(f"{API_URL}/v1.0/event/E2").mock(return_value=httpx.Response(200, json={}))
    async with HarmonyClient(_settings()) as shared:
        await events.events_get_by_id(_settings(), "E1", client=shared)
        await events.events_get_by_id(_settings(), "E2", client=shared)
    assert auth.call_count == 1


def _event(eid):
    return {
        "eventId": eid, "type": "phishing", "severity": "4", "state": "remediated",
        "confidenceIndicator": "malicious", "eventCreated": "2026-05-28T00:00:00Z",
        "saas": "office365_emails", "senderAddress": "a@b.com",
        "description": "Phishing", "entityId": "ENT1", "entityLink": "https://x",
        "data": "HEAVY-BLOB", "additionalData": None, "actions": [{"x": 1}],
    }


@respx.mock
async def test_query_compacts_by_default():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(
        return_value=httpx.Response(200, json={
            "responseEnvelope": {"recordsNumber": 2, "scrollId": "S1"},
            "responseData": [_event("E1"), _event("E2")],
        })
    )
    out = await events.events_query(_settings(), filters={"startDate": "x", "endDate": "y"})
    rec = out["responseData"][0]
    assert rec["eventId"] == "E1"
    assert "data" not in rec and "actions" not in rec
    assert set(rec).issubset({
        "eventId", "type", "severity", "state", "confidenceIndicator",
        "eventCreated", "saas", "senderAddress", "description", "entityId", "entityLink",
    })
    assert out["responseEnvelope"]["scrollId"] == "S1"


@respx.mock
async def test_query_limit_truncates():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(
        return_value=httpx.Response(200, json={
            "responseData": [_event("E1"), _event("E2"), _event("E3")]
        })
    )
    out = await events.events_query(_settings(), filters={"startDate": "x"}, limit=2)
    assert len(out["responseData"]) == 2


@respx.mock
async def test_query_full_returns_verbatim():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(
        return_value=httpx.Response(200, json={"responseData": [_event("E1")]})
    )
    out = await events.events_query(_settings(), filters={"startDate": "x"}, full=True)
    assert out["responseData"][0]["data"] == "HEAVY-BLOB"


@respx.mock
async def test_events_query_requires_date():
    with pytest.raises(HarmonyError):
        await events.events_query(_settings(), filters={"severities": ["Critical"]})


@respx.mock
async def test_events_query_max_records_paginates():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(side_effect=[
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 3, "scrollId": "S1"}, "responseData": [_event("E1"), _event("E2")]}),
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 3, "scrollId": "S2"}, "responseData": [_event("E3")]}),
    ])
    out = await events.events_query(_settings(), filters={"startDate": "x"}, max_records=10)
    assert len(out["responseData"]) == 3
    assert "data" not in out["responseData"][0]


@respx.mock
async def test_events_query_count_only():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(return_value=httpx.Response(
        200, json={"responseEnvelope": {"recordsNumber": 42}, "responseData": [_event("E1"), {**_event("E2"), "type": "spam"}]}))
    out = await events.events_query(_settings(), filters={"startDate": "x"}, count_only=True)
    assert out["recordsNumber"] == 42
    assert out["histogram"]["phishing"] == 1 and out["histogram"]["spam"] == 1
    assert "responseData" not in out


@respx.mock
async def test_events_query_cleans_description():
    _auth()
    ev = {**_event("E1"), "description": 'User #{"label": "alice@x.com"} reported phishing'}
    respx.post(f"{API_URL}/v1.0/event/query").mock(return_value=httpx.Response(200, json={"responseData": [ev]}))
    out = await events.events_query(_settings(), filters={"startDate": "x"})
    assert out["responseData"][0]["description"] == "User alice@x.com reported phishing"


@respx.mock
async def test_events_find_by_sender():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 2, "scrollId": ""},
        "responseData": [
            {**_event("E1"), "senderAddress": "bad@x.com"},
            {**_event("E2"), "senderAddress": "ok@y.com"},
        ]}))
    out = await events.events_find(_settings(), sender="BAD@x.com", start_date="2026-06-01T00:00:00Z")
    assert len(out["matches"]) == 1
    assert out["matches"][0]["eventId"] == "E1"
    assert out["pagesScanned"] == 1 and out["scanCapHit"] is False


@respx.mock
async def test_events_find_requires_filter_and_date():
    with pytest.raises(HarmonyError):
        await events.events_find(_settings(), start_date="2026-06-01T00:00:00Z")
    with pytest.raises(HarmonyError):
        await events.events_find(_settings(), sender="x@y.com")


@respx.mock
async def test_events_action_wait_returns_final_state():
    _auth()
    respx.post(f"{API_URL}/v1.0/action/event").mock(return_value=httpx.Response(
        200, json={"responseData": [{"eventId": "E1", "entityId": "ENT1", "taskId": "T7"}]}))
    respx.get(f"{API_URL}/v1.0/task/T7").mock(return_value=httpx.Response(
        200, json={"responseData": {"actions": [{"action_status": "completed", "action_message": "ok"}]}}))
    respx.get(f"{API_URL}/v1.0/search/entity/ENT1").mock(return_value=httpx.Response(
        200, json={"responseData": [{"entityInfo": {"entityId": "ENT1", "entityActionState": "quarantined"}, "entityPayload": {"isQuarantined": True, "isRestored": False}}]}))
    out = await events.events_action(_settings(), event_ids=["E1"], event_action_name="quarantine", timeout=0)
    assert out["status"] == "completed"
    assert out["taskId"] == "T7"
    assert out["finalState"]["isQuarantined"] is True


@respx.mock
async def test_events_action_no_wait_returns_taskid():
    _auth()
    respx.post(f"{API_URL}/v1.0/action/event").mock(return_value=httpx.Response(
        200, json={"responseData": [{"eventId": "E1", "entityId": "ENT1", "taskId": "T7"}]}))
    out = await events.events_action(_settings(), event_ids=["E1"], event_action_name="quarantine", wait=False)
    assert out["responseData"][0]["taskId"] == "T7"


@respx.mock
async def test_events_get_task_status_normalized():
    _auth()
    respx.get(f"{API_URL}/v1.0/task/T7").mock(return_value=httpx.Response(
        200, json={"responseData": {"actions": [{"action_status": "completed"}], "status": "inprogress"}}))
    out = await events.events_get_task_status(_settings(), task_id="T7")
    assert out["status"] == "completed"


@respx.mock
async def test_events_find_scan_cap_hit():
    _auth()
    respx.post(f"{API_URL}/v1.0/event/query").mock(return_value=httpx.Response(200, json={
        "responseEnvelope": {"recordsNumber": 999, "scrollId": "S1"},
        "responseData": [{**_event("E1"), "senderAddress": "bad@x.com"}]}))
    out = await events.events_find(
        _settings(), sender="bad@x.com", start_date="2026-06-01T00:00:00Z", max_pages=1
    )
    assert out["scanCapHit"] is True
    assert out["pagesScanned"] == 1
    assert len(out["matches"]) == 1
