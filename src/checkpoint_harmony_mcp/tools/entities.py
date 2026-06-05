from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ..errors import HarmonyError
from ._common import acquire_client, apply_view, paginate, record_matches


def _compact_entity(entity: dict[str, Any]) -> dict[str, Any]:
    """Curated subset of a secured entity for chat-friendly triage output."""
    info = entity.get("entityInfo") or {}
    payload = entity.get("entityPayload") or {}
    sec = entity.get("entitySecurityResult") or {}
    out: dict[str, Any] = {}
    for k in ("entityId", "saasEntityType", "entityActionState"):
        if k in info:
            out[k] = info[k]
    for k in ("subject", "fromEmail", "fromDomain", "recipients", "received",
              "isQuarantined", "SpfResult"):
        if k in payload:
            out[k] = payload[k]
    if "combinedVerdict" in sec:
        out["combinedVerdict"] = sec["combinedVerdict"]
    return out


async def entities_get_by_id(
    settings: Settings, entity_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Retrieve all details for a secured entity (email/file/message) by its entity ID."""
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/search/entity/{entity_id}")


async def entities_query(
    settings: Settings,
    entity_filter: dict[str, Any],
    extended_filter: list[Any] | None = None,
    scroll_id: str | None = None,
    limit: int = 25,
    full: bool = False,
    max_records: int | None = None,
    count_only: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Search secured entities. `entity_filter` requires `saas` and `startDate`.
    `max_records` (cap 500) auto-paginates and governs the returned count (overrides
    `limit`). `count_only=True` returns {recordsNumber, histogram}. `full=True` for raw."""
    request_data: dict[str, Any] = {"entityFilter": entity_filter}
    if extended_filter is not None:
        request_data["entityExtendedFilter"] = extended_filter
    if scroll_id is not None:
        request_data["scrollId"] = scroll_id
    async with acquire_client(settings, client) as c:
        if count_only:
            resp = await c.post("/v1.0/search/query", json={"requestData": request_data})
            hist: dict[str, int] = {}
            for ent in resp.get("responseData") or []:
                v = ((ent.get("entitySecurityResult") or {}).get("combinedVerdict") or {}).get("ap") or "unknown"
                hist[v] = hist.get(v, 0) + 1
            return {"recordsNumber": (resp.get("responseEnvelope") or {}).get("recordsNumber"), "histogram": hist}
        if max_records is not None:
            records, env, truncated = await paginate(c, "/v1.0/search/query", request_data, max_records)
            data = records if full else [_compact_entity(r) for r in records]
            out = {"responseEnvelope": env, "responseData": data}
            if truncated:
                out["truncated"] = True
            return out
        resp = await c.post("/v1.0/search/query", json={"requestData": request_data})
    return apply_view(resp, limit, full, _compact_entity)


async def entities_find(
    settings: Settings,
    *,
    message_id: str | None = None,
    sender: str | None = None,
    recipient: str | None = None,
    subject_contains: str | None = None,
    entity_id: str | None = None,
    saas: str = "office365_emails",
    start_date: str | None = None,
    end_date: str | None = None,
    max_pages: int = 20,
    full: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Find secured entities by message_id / sender / recipient / subject_contains /
    entity_id within a date window, paginating internally. Returns
    {matches, pagesScanned, scanCapHit, totalInWindow}. Requires start_date and >=1 filter."""
    if not start_date:
        raise HarmonyError("entities_find requires start_date")
    if not any([message_id, sender, recipient, subject_contains, entity_id]):
        raise HarmonyError("entities_find requires at least one filter (message_id/sender/recipient/subject_contains/entity_id)")
    ent_filter = {"saas": saas, "startDate": start_date}
    if end_date:
        ent_filter["endDate"] = end_date
    matches: list[dict[str, Any]] = []
    pages = 0
    scan_cap_hit = False
    total = None
    rd: dict[str, Any] = {"entityFilter": ent_filter}
    async with acquire_client(settings, client) as c:
        while True:
            resp = await c.post("/v1.0/search/query", json={"requestData": rd})
            env = resp.get("responseEnvelope") or {}
            if total is None:
                total = env.get("recordsNumber")
            page = resp.get("responseData") or []
            for ent in page:
                payload = ent.get("entityPayload") or {}
                info = ent.get("entityInfo") or {}
                comps = []
                if message_id:
                    comps.append((payload.get("internetMessageId"), message_id, "exact"))
                if sender:
                    comps.append((payload.get("fromEmail"), sender, "exact"))
                if recipient:
                    comps.append((payload.get("recipients"), recipient, "in"))
                if subject_contains:
                    comps.append((payload.get("subject"), subject_contains, "contains"))
                if entity_id:
                    comps.append((info.get("entityId"), entity_id, "exact"))
                if record_matches(comps):
                    matches.append(ent if full else _compact_entity(ent))
            pages += 1
            scroll = env.get("scrollId")
            if not page or not scroll:
                break
            if pages >= max_pages:
                scan_cap_hit = True
                break
            rd = {"entityFilter": ent_filter, "scrollId": scroll}
    return {"matches": matches, "pagesScanned": pages, "scanCapHit": scan_cap_hit, "totalInWindow": total}


async def entities_action(
    settings: Settings,
    entity_ids: list[str],
    entity_type: str,
    entity_action_name: str,
    entity_action_param: str | None = None,
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Perform an action (e.g. quarantine, restore) on one or more secured entities."""
    request_data: dict[str, Any] = {
        "entityIds": entity_ids,
        "entityType": entity_type,
        "entityActionName": entity_action_name,
    }
    if entity_action_param is not None:
        request_data["entityActionParam"] = entity_action_param
    if scope is not None:
        request_data["scope"] = scope
    async with acquire_client(settings, client) as c:
        return await c.post("/v1.0/action/entity", json={"requestData": request_data})


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="entities_get_by_id")
    async def _entities_get_by_id(entity_id: str) -> dict[str, Any]:
        """Retrieve all details for a secured entity (email/file/message) by its entity ID."""
        return await entities_get_by_id(settings, entity_id, client=client)

    @app.tool(name="entities_query")
    async def _entities_query(
        entity_filter: dict[str, Any], extended_filter: list[Any] | None = None,
        scroll_id: str | None = None, limit: int = 25, full: bool = False,
        max_records: int | None = None, count_only: bool = False,
    ) -> dict[str, Any]:
        """Search entities (entity_filter requires saas + startDate). Returns up to `limit`
        compact records, or `max_records` (cap 500) to auto-paginate, or `count_only=True`
        for {recordsNumber, histogram}. `full=True` for raw objects."""
        return await entities_query(
            settings, entity_filter, extended_filter, scroll_id,
            limit=limit, full=full, max_records=max_records, count_only=count_only, client=client,
        )

    @app.tool(name="entities_find")
    async def _entities_find(
        message_id: str | None = None, sender: str | None = None,
        recipient: str | None = None, subject_contains: str | None = None,
        entity_id: str | None = None, saas: str = "office365_emails",
        start_date: str | None = None, end_date: str | None = None,
        max_pages: int = 20, full: bool = False,
    ) -> dict[str, Any]:
        """Find emails/entities by message_id/sender/recipient/subject_contains/entity_id
        within a date window (start_date required, >=1 filter). Returns matches + scan metadata."""
        return await entities_find(
            settings, message_id=message_id, sender=sender, recipient=recipient,
            subject_contains=subject_contains, entity_id=entity_id, saas=saas,
            start_date=start_date, end_date=end_date, max_pages=max_pages, full=full, client=client,
        )

    @app.tool(name="entities_action")
    async def _entities_action(
        entity_ids: list[str],
        entity_type: str,
        entity_action_name: str,
        entity_action_param: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """Perform an action (e.g. quarantine, restore) on one or more secured entities."""
        return await entities_action(
            settings,
            entity_ids,
            entity_type,
            entity_action_name,
            entity_action_param,
            scope,
            client=client,
        )
