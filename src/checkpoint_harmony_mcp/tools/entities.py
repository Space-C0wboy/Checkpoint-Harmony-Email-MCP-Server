import base64
import json
import re
from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ..errors import HarmonyError
from ._common import (
    acquire_client,
    aggregate_action_results,
    apply_view,
    default_window,
    paginate,
    wait_for_task,
)

_FILENAME_RE = re.compile(r'filename\*?=("([^"]+)"|([^;]+))', re.IGNORECASE)


def _parse_filename(disposition: str | None, entity_id: str) -> str:
    if not disposition:
        return f"{entity_id}.eml"
    m = _FILENAME_RE.search(disposition)
    if not m:
        return f"{entity_id}.eml"
    return (m.group(2) or m.group(3) or f"{entity_id}.eml").strip()


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


async def entities_download(
    settings: Settings, entity_id: str, original: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Download a secured-entity email as RFC822 (.eml). Returns
    ``{filename, contentType, sizeBytes, base64}``. ``original=True`` returns the
    unmodified original message; default ``False`` adds Check Point visibility headers."""
    params = {"original": "true"} if original else None
    async with acquire_client(settings, client) as c:
        content, headers = await c.get_bytes(f"/v1.0/download/entity/{entity_id}", params=params)
    return {
        "filename": _parse_filename(headers.get("Content-Disposition"), entity_id),
        "contentType": headers.get("Content-Type", "application/octet-stream"),
        "sizeBytes": len(content),
        "base64": base64.b64encode(content).decode("ascii"),
    }


async def entities_query(
    settings: Settings,
    entity_filter: dict[str, Any],
    extended_filter: list[dict[str, Any]] | str | None = None,
    scroll_id: str | None = None,
    limit: int = 25,
    full: bool = False,
    max_records: int | None = None,
    count_only: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Search secured entities. `entity_filter` requires `saas` and `startDate`.
    `extended_filter` is an opaque list of {saasAttrName, saasAttrOp, saasAttrValue}
    objects pushed to the API for server-side filtering. Documented operators:
    is, contains, startsWith, isEmpty, isNot, notContains, isNotEmpty, greaterThan,
    lessThan. `saasAttrName` uses dotted paths like 'entityPayload.fromEmail',
    'entityPayload.subject', 'entityPayload.attachmentCount'.

    `max_records` (cap 500) auto-paginates and governs the returned count (overrides
    `limit`). `count_only=True` returns {recordsNumber, histogram}. `full=True` for raw."""
    if isinstance(extended_filter, str):
        try:
            extended_filter = json.loads(extended_filter)
        except json.JSONDecodeError as exc:
            raise HarmonyError(f"extended_filter must be a JSON array: {exc}") from exc
    if extended_filter is not None and not isinstance(extended_filter, list):
        raise HarmonyError(
            "extended_filter must be a list of {saasAttrName, saasAttrOp, saasAttrValue} objects"
        )
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
    limit: int = 25,
    max_records: int = 100,
    full: bool = False,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Locate a specific email/entity by sender, recipient, subject, or message-ID.
    Filters server-side (entityExtendedFilter) and auto-relaxes exact->contains;
    defaults to the last 30 days. Returns {matches, matchMode, totalInWindow, truncated}.
    Requires >=1 filter; start_date/end_date are optional."""
    if not any([message_id, sender, recipient, subject_contains, entity_id]):
        raise HarmonyError(
            "entities_find requires at least one filter "
            "(message_id/sender/recipient/subject_contains/entity_id)"
        )

    # entity_id-only: a direct lookup beats a filtered search.
    if entity_id and not any([message_id, sender, recipient, subject_contains]):
        async with acquire_client(settings, client) as c:
            resp = await c.get(f"/v1.0/search/entity/{entity_id}")
        rows = resp.get("responseData") or []
        matches = rows if full else [_compact_entity(r) for r in rows]
        return {"matches": matches[:limit], "matchMode": "exact",
                "totalInWindow": len(rows), "truncated": False}

    ent_filter: dict[str, Any] = {"saas": saas, "startDate": default_window(start_date)}
    if end_date:
        ent_filter["endDate"] = end_date

    # (saasAttrName, value, exact_op): exact_op is the op used in the exact pass;
    # fields that are inherently substring/list use "contains" in both passes.
    specs: list[tuple[str, str, str]] = []
    if sender:
        specs.append(("entityPayload.fromEmail", sender, "is"))
    if message_id:
        specs.append(("entityPayload.internetMessageId", message_id, "is"))
    if recipient:
        specs.append(("entityPayload.recipients", recipient, "contains"))
    if subject_contains:
        specs.append(("entityPayload.subject", subject_contains, "contains"))
    if entity_id:
        specs.append(("entityInfo.entityId", entity_id, "is"))

    def _build(relax: bool) -> list[dict[str, Any]]:
        return [
            {"saasAttrName": name, "saasAttrValue": value,
             "saasAttrOp": "contains" if (relax and exact_op == "is") else exact_op}
            for name, value, exact_op in specs
        ]

    has_exact = any(exact_op == "is" for _, _, exact_op in specs)

    async with acquire_client(settings, client) as c:
        rd = {"entityFilter": ent_filter, "entityExtendedFilter": _build(relax=False)}
        records, env, truncated = await paginate(c, "/v1.0/search/query", rd, max_records)
        mode = "exact" if has_exact else "contains"
        if not records and has_exact:
            rd = {"entityFilter": ent_filter, "entityExtendedFilter": _build(relax=True)}
            records, env, truncated = await paginate(c, "/v1.0/search/query", rd, max_records)
            mode = "contains"

    shown = records if full else [_compact_entity(r) for r in records]
    shown = shown[:limit]
    total = env.get("recordsNumber")
    more = truncated or (isinstance(total, int) and total > len(shown))
    if not records:
        mode = "none"
    return {"matches": shown, "matchMode": mode, "totalInWindow": total, "truncated": bool(more)}


async def entities_action(
    settings: Settings,
    entity_ids: list[str],
    entity_type: str,
    entity_action_name: str,
    entity_action_param: Any = None,
    wait: bool = True,
    timeout: int = 60,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Perform an action (e.g. quarantine, restore) on one or more secured entities.
    ``entity_type`` is required (e.g. ``office365_emails_email``) — it is the
    ``saasEntityType`` of the target entities, returned by entities_query/entities_find.
    Waits by default. Multi-ID + wait returns ``{tasks, summary}``; single-ID + wait
    returns ``{taskId, status, finalState, raw}``."""
    request_data: dict[str, Any] = {
        "entityIds": entity_ids,
        "entityType": entity_type,
        "entityActionName": entity_action_name,  # scalar enum name
    }
    if entity_action_param is not None:
        request_data["entityActionParam"] = entity_action_param  # scalar
    async with acquire_client(settings, client) as c:
        resp = await c.post("/v1.0/action/entity", json={"requestData": request_data})
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
        return {
            "taskId": task_id, "status": norm["status"], "message": norm.get("message"),
            "finalState": final_state, "finalStateSettled": norm["status"] == "completed",
            "timedOut": norm.get("timedOut", False), "raw": resp,
        }


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="entities_get_by_id")
    async def _entities_get_by_id(entity_id: str) -> dict[str, Any]:
        """Retrieve all details for a secured entity (email/file/message) by its entity ID."""
        return await entities_get_by_id(settings, entity_id, client=client)

    @app.tool(name="entities_download")
    async def _entities_download(entity_id: str, original: bool = False) -> dict[str, Any]:
        """Download an entity (email) as .eml. Returns {filename, contentType, sizeBytes,
        base64}. original=True for the unmodified message."""
        return await entities_download(settings, entity_id, original=original, client=client)

    @app.tool(name="entities_query")
    async def _entities_query(
        entity_filter: dict[str, Any], extended_filter: list[dict[str, Any]] | None = None,
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
        limit: int = 25, max_records: int = 100, full: bool = False,
    ) -> dict[str, Any]:
        """Locate a specific email/entity by sender, recipient, subject, or message-ID.
        Filters server-side and auto-relaxes exact->contains; defaults to the last 30 days
        when start_date is omitted. Returns matches + {matchMode, totalInWindow, truncated}."""
        return await entities_find(
            settings, message_id=message_id, sender=sender, recipient=recipient,
            subject_contains=subject_contains, entity_id=entity_id, saas=saas,
            start_date=start_date, end_date=end_date, limit=limit, max_records=max_records,
            full=full, client=client,
        )

    @app.tool(name="entities_action")
    async def _entities_action(
        entity_ids: list[str], entity_type: str, entity_action_name: str,
        entity_action_param: Any = None,
        wait: bool = True, timeout: int = 60,
    ) -> dict[str, Any]:
        """Quarantine/restore one or more entities. entity_type is required (the entity's
        saasEntityType, e.g. office365_emails_email, from entities_query/entities_find).
        Waits by default; multi-ID returns tasks+summary, single-ID returns finalState."""
        return await entities_action(
            settings, entity_ids, entity_type, entity_action_name, entity_action_param,
            wait=wait, timeout=timeout, client=client,
        )
