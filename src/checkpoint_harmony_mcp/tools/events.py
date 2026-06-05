from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ..errors import HarmonyError
from ._common import acquire_client, apply_view, clean_description, paginate, record_matches

_EVENT_FIELDS = (
    "eventId", "type", "severity", "state", "confidenceIndicator", "eventCreated",
    "saas", "senderAddress", "description", "entityId", "entityLink",
)


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    """Curated subset of an event for chat-friendly triage output."""
    out = {k: event[k] for k in _EVENT_FIELDS if k in event}
    if "description" in out:
        out["description"] = clean_description(out["description"])
    return out


async def events_get_by_id(
    settings: Settings, event_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Retrieve a single security event by its Email Security event ID."""
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/event/{event_id}")


async def events_query(
    settings: Settings,
    filters: dict[str, Any],
    limit: int = 25,
    full: bool = False,
    max_records: int | None = None,
    count_only: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Query security events. `filters` accepts eventTypes, eventStates, severities,
    startDate, endDate, saas, description, eventIds, confidenceIndicator, scrollId.
    A date range is REQUIRED (startDate). `max_records` (cap 500) auto-paginates and
    governs the returned count (overrides `limit`). `count_only=True` returns
    {recordsNumber, histogram} with no records. `full=True` returns raw event objects."""
    if not filters.get("startDate"):
        raise HarmonyError("events require a date range: set startDate (and ideally endDate) in filters")
    async with acquire_client(settings, client) as c:
        if count_only:
            resp = await c.post("/v1.0/event/query", json={"requestData": filters})
            hist: dict[str, int] = {}
            for ev in resp.get("responseData") or []:
                t = ev.get("type") or "unknown"
                hist[t] = hist.get(t, 0) + 1
            return {"recordsNumber": (resp.get("responseEnvelope") or {}).get("recordsNumber"), "histogram": hist}
        if max_records is not None:
            records, env, truncated = await paginate(c, "/v1.0/event/query", filters, max_records)
            data = records if full else [_compact_event(r) for r in records]
            out = {"responseEnvelope": env, "responseData": data}
            if truncated:
                out["truncated"] = True
            return out
        resp = await c.post("/v1.0/event/query", json={"requestData": filters})
    return apply_view(resp, limit, full, _compact_event)


async def events_find(
    settings: Settings,
    *,
    sender: str | None = None,
    text_contains: str | None = None,
    entity_id: str | None = None,
    event_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    max_pages: int = 20,
    full: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Find security events by sender / text_contains (matches description) / entity_id /
    event_id within a date window, paginating internally. Returns
    {matches, pagesScanned, scanCapHit, totalInWindow}. Requires start_date and >=1 filter."""
    if not start_date:
        raise HarmonyError("events_find requires start_date")
    if not any([sender, text_contains, entity_id, event_id]):
        raise HarmonyError("events_find requires at least one filter (sender/text_contains/entity_id/event_id)")
    base = {"startDate": start_date}
    if end_date:
        base["endDate"] = end_date
    matches: list[dict[str, Any]] = []
    pages = 0
    scan_cap_hit = False
    total = None
    rd = dict(base)
    async with acquire_client(settings, client) as c:
        while True:
            resp = await c.post("/v1.0/event/query", json={"requestData": rd})
            env = resp.get("responseEnvelope") or {}
            if total is None:
                total = env.get("recordsNumber")
            page = resp.get("responseData") or []
            for ev in page:
                comps = []
                if sender:
                    comps.append((ev.get("senderAddress"), sender, "exact"))
                if text_contains:
                    comps.append((clean_description(ev.get("description")), text_contains, "contains"))
                if entity_id:
                    comps.append((ev.get("entityId"), entity_id, "exact"))
                if event_id:
                    comps.append((ev.get("eventId"), event_id, "exact"))
                if record_matches(comps):
                    matches.append(ev if full else _compact_event(ev))
            pages += 1
            scroll = env.get("scrollId")
            if not page or not scroll:
                break
            if pages >= max_pages:
                scan_cap_hit = True
                break
            rd = {**base, "scrollId": scroll}
    return {"matches": matches, "pagesScanned": pages, "scanCapHit": scan_cap_hit, "totalInWindow": total}


async def events_action(
    settings: Settings,
    event_ids: list[str],
    event_action_name: str,
    event_action_param: str | None = None,
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Perform an action (e.g. quarantine, dismiss) on one or more security events."""
    request_data: dict[str, Any] = {
        "eventIds": event_ids,
        "eventActionName": event_action_name,
    }
    if event_action_param is not None:
        request_data["eventActionParam"] = event_action_param
    if scope is not None:
        request_data["scope"] = scope
    async with acquire_client(settings, client) as c:
        return await c.post("/v1.0/action/event", json={"requestData": request_data})


async def events_get_task_status(
    settings: Settings, task_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Get the execution status of an action task created by events_action."""
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/task/{task_id}")


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="events_get_by_id")
    async def _events_get_by_id(event_id: str) -> dict[str, Any]:
        """Retrieve a single security event by its Email Security event ID."""
        return await events_get_by_id(settings, event_id, client=client)

    @app.tool(name="events_query")
    async def _events_query(
        filters: dict[str, Any], limit: int = 25, full: bool = False,
        max_records: int | None = None, count_only: bool = False,
    ) -> dict[str, Any]:
        """Query security events (requires startDate in filters). Returns up to `limit`
        compact records, or set `max_records` (cap 500) to auto-paginate, or
        `count_only=True` for {recordsNumber, histogram}. `full=True` for raw objects."""
        return await events_query(
            settings, filters, limit=limit, full=full,
            max_records=max_records, count_only=count_only, client=client,
        )

    @app.tool(name="events_find")
    async def _events_find(
        sender: str | None = None, text_contains: str | None = None,
        entity_id: str | None = None, event_id: str | None = None,
        start_date: str | None = None, end_date: str | None = None,
        max_pages: int = 20, full: bool = False,
    ) -> dict[str, Any]:
        """Find events by sender/text_contains/entity_id/event_id within a date window
        (start_date required, >=1 filter). Returns matches + scan metadata."""
        return await events_find(
            settings, sender=sender, text_contains=text_contains, entity_id=entity_id,
            event_id=event_id, start_date=start_date, end_date=end_date,
            max_pages=max_pages, full=full, client=client,
        )

    @app.tool(name="events_action")
    async def _events_action(
        event_ids: list[str],
        event_action_name: str,
        event_action_param: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """Perform an action (e.g. quarantine, dismiss) on one or more security events."""
        return await events_action(
            settings, event_ids, event_action_name, event_action_param, scope, client=client
        )

    @app.tool(name="events_get_task_status")
    async def _events_get_task_status(task_id: str) -> dict[str, Any]:
        """Get the execution status of an action task created by events_action."""
        return await events_get_task_status(settings, task_id, client=client)
