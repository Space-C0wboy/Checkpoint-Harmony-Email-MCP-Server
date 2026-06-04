from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ._common import acquire_client, apply_view

_EVENT_FIELDS = (
    "eventId", "type", "severity", "state", "confidenceIndicator", "eventCreated",
    "saas", "senderAddress", "description", "entityId", "entityLink",
)


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    """Curated subset of an event for chat-friendly triage output."""
    return {k: event[k] for k in _EVENT_FIELDS if k in event}


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
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Query security events. `filters` accepts eventTypes, eventStates, severities,
    startDate, endDate, saas, description, eventIds, confidenceIndicator, scrollId.
    NOTE: the API requires a date range -- include startDate (and endDate) or it errors.

    Returns at most `limit` records (default 25); pass `full=True` for complete event
    objects instead of the compact summary. Use the envelope's `scrollId` (via
    filters.scrollId) to page for more.
    """
    async with acquire_client(settings, client) as c:
        resp = await c.post("/v1.0/event/query", json={"requestData": filters})
    return apply_view(resp, limit, full, _compact_event)


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
        filters: dict[str, Any], limit: int = 25, full: bool = False
    ) -> dict[str, Any]:
        """Query security events. filters accepts eventTypes, eventStates, severities,
        startDate, endDate, saas, description, eventIds, confidenceIndicator, scrollId.
        A date range is required (startDate/endDate). Returns up to `limit` compact
        records; pass full=True for complete objects."""
        return await events_query(settings, filters, limit=limit, full=full, client=client)

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
