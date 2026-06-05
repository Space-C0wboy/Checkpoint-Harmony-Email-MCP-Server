from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ._common import acquire_client, apply_view, paginate


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
