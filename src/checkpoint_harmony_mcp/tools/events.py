from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ._common import acquire_client


async def events_get_by_id(
    settings: Settings, event_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Retrieve a single security event by its Email Security event ID."""
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/event/{event_id}")


async def events_query(
    settings: Settings, filters: dict[str, Any], client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Query security events. `filters` accepts eventTypes, eventStates, severities,
    startDate, endDate, saas, description, eventIds, confidenceIndicator, scrollId."""
    async with acquire_client(settings, client) as c:
        return await c.post("/v1.0/event/query", json={"requestData": filters})


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
    async def _events_query(filters: dict[str, Any]) -> dict[str, Any]:
        """Query security events. filters accepts eventTypes, eventStates, severities,
        startDate, endDate, saas, description, eventIds, confidenceIndicator, scrollId."""
        return await events_query(settings, filters, client=client)

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
