import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

from ..config import Settings


@asynccontextmanager
async def acquire_client(
    settings: Settings, client: "HarmonyClient | None"
) -> AsyncIterator["HarmonyClient"]:
    """Yield a shared client if provided, else a short-lived one bound to settings.

    A provided (shared) client is NOT closed here -- its lifetime is owned by the
    caller (the server). A short-lived client is opened and closed per call.
    """
    from ..client import HarmonyClient
    if client is not None:
        yield client
    else:
        async with HarmonyClient(settings) as owned:
            yield owned


def apply_view(
    resp: dict[str, Any],
    limit: int,
    full: bool,
    compactor: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Trim ``responseData`` to ``limit`` records and, unless ``full``, map each
    record through ``compactor``. ``responseEnvelope`` and all other keys are
    preserved. Returns ``resp`` unchanged when there is no non-empty list under
    ``responseData``. Does not mutate the input.
    """
    data = resp.get("responseData")
    if not isinstance(data, list) or not data:
        return resp
    # Clamp to avoid negative-index surprises (e.g. limit=-1 dropping the last record).
    sliced = data[: max(limit, 0)]
    new_data = sliced if full else [compactor(r) for r in sliced]
    return {**resp, "responseData": new_data}


_ENTITY_TOKEN = re.compile(r"#(\{.*?\})", re.DOTALL)


def clean_description(text):
    """Replace Harmony embedded-entity tokens (``#{...json...}``) with their human
    label, leaving surrounding text intact. Non-strings / token-free text pass through."""
    if not isinstance(text, str) or "#{" not in text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        try:
            obj = json.loads(m.group(1))
        except Exception:
            return ""
        return str(obj.get("label") or obj.get("display") or "")

    return _ENTITY_TOKEN.sub(_repl, text)


def _cmp(actual: Any, expected: str, mode: str) -> bool:
    e = (expected or "").lower()
    if mode == "exact":
        return isinstance(actual, str) and actual.lower() == e
    if mode == "contains":
        return isinstance(actual, str) and e in actual.lower()
    if mode == "in":
        return isinstance(actual, list) and any(isinstance(x, str) and x.lower() == e for x in actual)
    return False


def record_matches(comparisons: "list[tuple[Any, str, str]]") -> bool:
    """AND of (actual, expected, mode) comparisons. mode in {'exact','contains','in'};
    all case-insensitive. Caller includes only the filters that were provided."""
    return all(_cmp(actual, expected, mode) for actual, expected, mode in comparisons)


def normalize_task_status(task_json: dict[str, Any]) -> dict[str, Any]:
    """Derive a reliable task status from the inner per-action statuses (the outer
    ``status`` lags). Returns {status, message, actions, raw}."""
    actions = (task_json.get("responseData") or {}).get("actions") or []
    statuses = [a.get("action_status") for a in actions]
    if any(s == "failed" for s in statuses):
        status = "failed"
    elif actions and all(s == "completed" for s in statuses):
        status = "completed"
    else:
        status = "inprogress"
    inner = [{"name": a.get("action_name"), "status": a.get("action_status"), "message": a.get("action_message")} for a in actions]
    message = "; ".join(filter(None, (a.get("action_message") for a in actions)))
    return {"status": status, "message": message, "actions": inner, "raw": task_json}


_MAX_RECORDS_CAP = 500


async def paginate(client, path, request_data, max_records):
    """POST {requestData: request_data} to ``path``, follow ``scrollId`` and aggregate
    ``responseData`` up to ``max_records`` (clamped to 500). Returns
    (records, last_envelope, truncated). ``truncated`` is True if the cap was hit while
    more records remained."""
    cap = max(1, min(int(max_records), _MAX_RECORDS_CAP))
    records: list[Any] = []
    envelope: dict[str, Any] = {}
    rd = dict(request_data)
    truncated = False
    while True:
        resp = await client.post(path, json={"requestData": rd})
        envelope = resp.get("responseEnvelope") or {}
        page = resp.get("responseData") or []
        records.extend(page)
        scroll = envelope.get("scrollId")
        total = envelope.get("recordsNumber")
        if len(records) >= cap:
            # Only truncated if records beyond the cap actually remain. If the cap
            # happens to equal the total available, nothing is dropped.
            exhausted = isinstance(total, int) and cap >= total
            truncated = bool(scroll) and len(page) > 0 and not exhausted
            records = records[:cap]
            break
        if isinstance(total, int) and len(records) >= total:
            break
        if not page or not scroll:
            break
        rd = {**request_data, "scrollId": scroll}
    return records, envelope, truncated


async def wait_for_task(client, task_id, timeout=60, interval=5):
    """Poll /v1.0/task/{task_id}, normalizing status, until terminal or ``timeout``
    seconds. Returns the normalized status dict; sets ``timedOut`` True on timeout."""
    elapsed = 0
    while True:
        norm = normalize_task_status(await client.get(f"/v1.0/task/{task_id}"))
        if norm["status"] in ("completed", "failed"):
            return norm
        if elapsed >= timeout:
            norm["timedOut"] = True
            return norm
        await asyncio.sleep(interval)
        elapsed += interval


async def aggregate_action_results(
    client, rows: list[dict[str, Any]], timeout: int
) -> dict[str, Any]:
    """For a bulk-action ``responseData`` (list of {entityId, taskId, ...}), poll each
    task to terminal status in parallel and fetch each entity's post-action state.
    Returns ``{"tasks": [...], "summary": {total, completed, failed, inProgress, timedOut}}``."""

    async def _one(row: dict[str, Any]) -> dict[str, Any]:
        tid = row.get("taskId")
        eid = row.get("entityId")
        norm = await wait_for_task(client, tid, timeout=timeout) if tid else {"status": "failed", "message": "no taskId"}
        final_state = None
        if eid:
            try:
                ent = await client.get(f"/v1.0/search/entity/{eid}")
                ent_row = (ent.get("responseData") or [{}])[0]
                info = ent_row.get("entityInfo") or {}
                payload = ent_row.get("entityPayload") or {}
                final_state = {
                    "entityId": eid,
                    "isQuarantined": payload.get("isQuarantined"),
                    "isRestored": payload.get("isRestored"),
                    "entityActionState": info.get("entityActionState"),
                }
            except Exception:  # never let one entity fetch poison the whole result
                final_state = None
        return {
            "entityId": eid,
            "taskId": tid,
            "status": norm.get("status"),
            "message": norm.get("message"),
            "finalState": final_state,
            "timedOut": norm.get("timedOut", False),
        }

    tasks = await asyncio.gather(*[_one(r) for r in rows])
    summary = {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t["status"] == "completed"),
        "failed": sum(1 for t in tasks if t["status"] == "failed"),
        "inProgress": sum(1 for t in tasks if t["status"] == "inprogress"),
        "timedOut": sum(1 for t in tasks if t["timedOut"]),
    }
    return {"tasks": tasks, "summary": summary}


import time as _time_mod


class TokenBucket:
    """Async-safe token bucket. ``acquire()`` returns after a token is available;
    sleeps proportionally when the bucket is empty."""

    def __init__(self, rate_per_sec: float, burst: int):
        self._rate = float(rate_per_sec)
        self._capacity = float(burst)
        self._tokens = float(burst)
        self._last = _time_mod.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = _time_mod.monotonic()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            wait = (1.0 - self._tokens) / self._rate
        await asyncio.sleep(wait)
        async with self._lock:
            self._tokens = 0.0
            self._last = _time_mod.monotonic()
