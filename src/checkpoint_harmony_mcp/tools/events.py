from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ..errors import HarmonyError
from ._common import (
    acquire_client,
    aggregate_action_results,
    apply_view,
    clean_description,
    default_window,
    normalize_task_status,
    paginate,
    record_matches,
    wait_for_task,
)

_EVENT_FIELDS = (
    "eventId",
    "type",
    "severity",
    "state",
    "confidenceIndicator",
    "eventCreated",
    "saas",
    "senderAddress",
    "description",
    "entityId",
    "entityLink",
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
        raise HarmonyError(
            "events require a date range: set startDate (and ideally endDate) in filters"
        )
    async with acquire_client(settings, client) as c:
        if count_only:
            resp = await c.post("/v1.0/event/query", json={"requestData": filters})
            hist: dict[str, int] = {}
            for ev in resp.get("responseData") or []:
                t = ev.get("type") or "unknown"
                hist[t] = hist.get(t, 0) + 1
            return {
                "recordsNumber": (resp.get("responseEnvelope") or {}).get("recordsNumber"),
                "histogram": hist,
            }
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
    limit: int = 25,
    full: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Find security events by sender / text_contains / entity_id / event_id. Narrows
    server-side (a `description` substring pre-filter, or `eventIds` for event_id) then
    refines client-side, auto-relaxing exact->contains for sender. Defaults to the last
    30 days. Returns {matches, matchMode, pagesScanned, scanCapHit, totalInWindow,
    truncated}. `limit` (default 25) caps matches; the scan stops early once reached.
    Requires >=1 filter; start_date/end_date are optional."""
    if not any([sender, text_contains, entity_id, event_id]):
        raise HarmonyError(
            "events_find requires at least one filter (sender/text_contains/entity_id/event_id)"
        )
    base: dict[str, Any] = {"startDate": default_window(start_date)}
    if end_date:
        base["endDate"] = end_date
    if event_id:
        base["eventIds"] = [event_id]
    else:
        # Prefer sender for the server-side description pre-filter (more selective);
        # fall back to text_contains. Client-side refinement still applies all filters.
        prefilter = sender or text_contains
        if prefilter:
            base["description"] = prefilter

    async def _scan(c: HarmonyClient, sender_mode: str) -> tuple[list, int, bool, Any, bool]:
        matches: list[dict[str, Any]] = []
        pages = 0
        scan_cap_hit = False
        limit_hit = False
        total: Any = None
        rd = dict(base)
        while True:
            resp = await c.post("/v1.0/event/query", json={"requestData": rd})
            env = resp.get("responseEnvelope") or {}
            if total is None:
                total = env.get("recordsNumber")
            page = resp.get("responseData") or []
            for ev in page:
                comps = []
                if sender:
                    comps.append((ev.get("senderAddress"), sender, sender_mode))
                if text_contains:
                    comps.append(
                        (clean_description(ev.get("description")), text_contains, "contains")
                    )
                if entity_id:
                    comps.append((ev.get("entityId"), entity_id, "exact"))
                if event_id:
                    comps.append((ev.get("eventId"), event_id, "exact"))
                if record_matches(comps):
                    matches.append(ev if full else _compact_event(ev))
            pages += 1
            scroll = env.get("scrollId")
            # Natural exhaustion first: if the window is fully seen, it is not truncated
            # even if we happened to reach the limit on the final page.
            if not page or not scroll:
                break
            if len(matches) >= limit:
                limit_hit = True
                break
            if pages >= max_pages:
                scan_cap_hit = True
                break
            rd = {**base, "scrollId": scroll}
        return matches[:limit], pages, scan_cap_hit, total, limit_hit

    async with acquire_client(settings, client) as c:
        matches, pages, scan_cap_hit, total, limit_hit = await _scan(c, "exact")
        mode = "exact"
        if not matches and sender:
            # The description pre-filter still narrows server-side; only the client-side
            # sender comparison relaxes from exact to contains on this second pass.
            matches, pages, scan_cap_hit, total, limit_hit = await _scan(c, "contains")
            mode = "contains"
    if not matches:
        mode = "none"
    elif not sender:
        # No sender relaxation applies. Report "exact" only for exact-identifier matches
        # (event_id/entity_id); a text_contains-only match is inherently substring.
        mode = "exact" if (event_id or entity_id) else "contains"
    return {
        "matches": matches,
        "matchMode": mode,
        "pagesScanned": pages,
        "scanCapHit": scan_cap_hit,
        "totalInWindow": total,
        "truncated": limit_hit or scan_cap_hit,
    }


async def events_action(
    settings: Settings,
    event_ids: list[str],
    event_action_name: str,
    event_action_param: Any = None,
    wait: bool = True,
    timeout: int = 60,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Perform an action on one or more security events. Known verbs:
    ``quarantine``, ``restore``, ``dismiss``, ``severityChange``, ``senttoadmin``.
    For ``severityChange`` pass ``event_action_param`` as a dict matching
    ``{"newSeverity": "Low|Medium|High|Highest"}`` per the API guide.

    Waits by default. With multiple ``event_ids`` and ``wait=True`` returns
    ``{tasks:[...], summary:{...}}``; single-ID + wait returns
    ``{taskId, status, finalState, raw}``; ``wait=False`` returns the raw POST result."""
    request_data: dict[str, Any] = {
        "eventIds": event_ids,
        "eventActionName": event_action_name,  # scalar enum name
    }
    if event_action_param is not None:
        request_data["eventActionParam"] = event_action_param  # scalar
    async with acquire_client(settings, client) as c:
        resp = await c.post("/v1.0/action/event", json={"requestData": request_data})
        if not wait:
            return resp
        rows = resp.get("responseData") or []
        if len(rows) > 1:
            agg = await aggregate_action_results(c, rows, timeout=timeout)
            agg["raw"] = resp
            return agg
        first = rows[0] if rows else {}
        task_id = first.get("taskId")
        entity_id = first.get("entityId")
        if not task_id:
            return resp
        norm = await wait_for_task(c, task_id, timeout=timeout)
        final_state = None
        settled = False
        if entity_id:
            ent = await c.get(f"/v1.0/search/entity/{entity_id}")
            row = (ent.get("responseData") or [{}])[0]
            info = row.get("entityInfo") or {}
            payload = row.get("entityPayload") or {}
            final_state = {
                "entityId": entity_id,
                "isQuarantined": payload.get("isQuarantined"),
                "isRestored": payload.get("isRestored"),
                "entityActionState": info.get("entityActionState"),
            }
            settled = norm["status"] == "completed"
        return {
            "taskId": task_id,
            "status": norm["status"],
            "message": norm.get("message"),
            "finalState": final_state,
            "finalStateSettled": settled,
            "timedOut": norm.get("timedOut", False),
            "raw": resp,
        }


async def events_get_task_status(
    settings: Settings, task_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Get the normalized status of an action task (derived from inner action statuses;
    the upstream outer status lags). Returns {status, message, actions, raw}."""
    async with acquire_client(settings, client) as c:
        return normalize_task_status(await c.get(f"/v1.0/task/{task_id}"))


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="events_get_by_id")
    async def _events_get_by_id(event_id: str) -> dict[str, Any]:
        """Retrieve a single security event by its Email Security event ID."""
        return await events_get_by_id(settings, event_id, client=client)

    @app.tool(name="events_query")
    async def _events_query(
        filters: dict[str, Any],
        limit: int = 25,
        full: bool = False,
        max_records: int | None = None,
        count_only: bool = False,
    ) -> dict[str, Any]:
        """Query security events (requires startDate in filters). Returns up to `limit`
        compact records, or set `max_records` (cap 500) to auto-paginate, or
        `count_only=True` for {recordsNumber, histogram}. `full=True` for raw objects."""
        return await events_query(
            settings,
            filters,
            limit=limit,
            full=full,
            max_records=max_records,
            count_only=count_only,
            client=client,
        )

    @app.tool(name="events_find")
    async def _events_find(
        sender: str | None = None,
        text_contains: str | None = None,
        entity_id: str | None = None,
        event_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        max_pages: int = 20,
        limit: int = 25,
        full: bool = False,
    ) -> dict[str, Any]:
        """Find events by sender/text_contains/entity_id/event_id. Narrows server-side
        then refines (auto-relaxes exact->contains for sender); defaults to the last 30
        days. `limit` (default 25) caps matches. Returns matches +
        {matchMode, pagesScanned, scanCapHit, totalInWindow, truncated}."""
        return await events_find(
            settings,
            sender=sender,
            text_contains=text_contains,
            entity_id=entity_id,
            event_id=event_id,
            start_date=start_date,
            end_date=end_date,
            max_pages=max_pages,
            limit=limit,
            full=full,
            client=client,
        )

    @app.tool(name="events_action")
    async def _events_action(
        event_ids: list[str],
        event_action_name: str,
        event_action_param: Any = None,
        wait: bool = True,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """Act on one or more events. Verbs: quarantine, restore, dismiss, severityChange,
        senttoadmin. For severityChange pass event_action_param as
        {"newSeverity": "Low|Medium|High|Highest"}. Waits for completion by default
        (multi-ID returns tasks+summary; single-ID returns finalState). wait=false for fire-and-forget."""
        return await events_action(
            settings,
            event_ids,
            event_action_name,
            event_action_param,
            wait=wait,
            timeout=timeout,
            client=client,
        )

    @app.tool(name="events_get_task_status")
    async def _events_get_task_status(task_id: str) -> dict[str, Any]:
        """Normalized status of an action task ({status, message, actions, raw})."""
        return await events_get_task_status(settings, task_id, client=client)
