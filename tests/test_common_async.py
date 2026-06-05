import time as _time

import httpx
import respx

from checkpoint_harmony_mcp.client import HarmonyClient
from checkpoint_harmony_mcp.config import Settings
from checkpoint_harmony_mcp.tools._common import (
    TokenBucket,
    aggregate_action_results,
    paginate,
    wait_for_task,
)

AUTH = "https://gw.example/auth/external"
API = "https://gw.example/app/hec-api"


def _settings():
    return Settings(checkpoint_client_id="c", checkpoint_secret="s",
                    checkpoint_auth_url=AUTH, checkpoint_api_url=API, checkpoint_scope="s1")


def _auth():
    respx.post(AUTH).mock(return_value=httpx.Response(200, json={"success": True, "data": {"token": "t"}}))


@respx.mock
async def test_paginate_aggregates_until_scroll_exhausted():
    _auth()
    respx.post(f"{API}/v1.0/search/query").mock(side_effect=[
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 3, "scrollId": "S1"}, "responseData": [{"id": 1}, {"id": 2}]}),
        httpx.Response(200, json={"responseEnvelope": {"recordsNumber": 3, "scrollId": "S2"}, "responseData": [{"id": 3}]}),
    ])
    async with HarmonyClient(_settings()) as c:
        records, env, truncated = await paginate(c, "/v1.0/search/query", {"entityFilter": {}}, max_records=100)
    assert [r["id"] for r in records] == [1, 2, 3]
    assert truncated is False


@respx.mock
async def test_paginate_stops_at_cap_and_flags_truncated():
    _auth()
    respx.post(f"{API}/v1.0/search/query").mock(return_value=httpx.Response(
        200, json={"responseEnvelope": {"recordsNumber": 9, "scrollId": "S1"}, "responseData": [{"id": 1}, {"id": 2}]}))
    async with HarmonyClient(_settings()) as c:
        records, env, truncated = await paginate(c, "/v1.0/search/query", {"entityFilter": {}}, max_records=2)
    assert len(records) == 2
    assert truncated is True


@respx.mock
async def test_wait_for_task_returns_on_completed():
    _auth()
    respx.get(f"{API}/v1.0/task/T1").mock(side_effect=[
        httpx.Response(200, json={"responseData": {"actions": [{"action_status": "init"}]}}),
        httpx.Response(200, json={"responseData": {"actions": [{"action_status": "completed", "action_message": "ok"}]}}),
    ])
    async with HarmonyClient(_settings()) as c:
        out = await wait_for_task(c, "T1", timeout=5, interval=0)
    assert out["status"] == "completed"


@respx.mock
async def test_wait_for_task_times_out():
    _auth()
    respx.get(f"{API}/v1.0/task/T1").mock(return_value=httpx.Response(200, json={"responseData": {"actions": [{"action_status": "init"}]}}))
    async with HarmonyClient(_settings()) as c:
        out = await wait_for_task(c, "T1", timeout=0, interval=0)
    assert out["status"] == "inprogress"
    assert out["timedOut"] is True


@respx.mock
async def test_paginate_not_truncated_when_cap_equals_total():
    _auth()
    respx.post(f"{API}/v1.0/search/query").mock(return_value=httpx.Response(
        200, json={"responseEnvelope": {"recordsNumber": 2, "scrollId": "S1"}, "responseData": [{"id": 1}, {"id": 2}]}))
    async with HarmonyClient(_settings()) as c:
        records, env, truncated = await paginate(c, "/v1.0/search/query", {"entityFilter": {}}, max_records=2)
    assert len(records) == 2
    assert truncated is False


async def test_token_bucket_throttles_to_rate():
    # rate=2/sec, burst=2 -> 4 acquires should take at least ~1.0s (2 free, then 1 every 0.5s)
    b = TokenBucket(rate_per_sec=2.0, burst=2)
    start = _time.monotonic()
    for _ in range(4):
        await b.acquire()
    elapsed = _time.monotonic() - start
    assert elapsed >= 0.9, f"expected throttling, took only {elapsed:.2f}s"


@respx.mock
async def test_aggregate_action_results_polls_each_task_and_fetches_entity_state():
    _auth()
    respx.get(f"{API}/v1.0/task/T1").mock(return_value=httpx.Response(
        200, json={"responseData": {"actions": [{"action_status": "completed"}]}}))
    respx.get(f"{API}/v1.0/task/T2").mock(return_value=httpx.Response(
        200, json={"responseData": {"actions": [{"action_status": "failed", "action_message": "denied"}]}}))
    respx.get(f"{API}/v1.0/search/entity/ENT1").mock(return_value=httpx.Response(
        200, json={"responseData": [{"entityInfo": {"entityId": "ENT1", "entityActionState": "quarantined"},
                                       "entityPayload": {"isQuarantined": True, "isRestored": False}}]}))
    respx.get(f"{API}/v1.0/search/entity/ENT2").mock(return_value=httpx.Response(
        200, json={"responseData": [{"entityInfo": {"entityId": "ENT2", "entityActionState": "links_replaced"},
                                       "entityPayload": {"isQuarantined": False, "isRestored": False}}]}))
    async with HarmonyClient(_settings()) as c:
        out = await aggregate_action_results(
            c,
            [{"entityId": "ENT1", "taskId": "T1"}, {"entityId": "ENT2", "taskId": "T2"}],
            timeout=0,
        )
    assert {t["entityId"] for t in out["tasks"]} == {"ENT1", "ENT2"}
    assert out["summary"] == {"total": 2, "completed": 1, "failed": 1, "inProgress": 0, "timedOut": 0}
