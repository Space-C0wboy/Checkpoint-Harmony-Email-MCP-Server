from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ._common import acquire_client


def _scope_params(scope: str | None) -> dict[str, Any] | None:
    return {"scope": scope} if scope is not None else None


async def exceptions_list(
    settings: Settings,
    exc_type: str,
    exc_id: str | None = None,
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """List exceptions of a given type (e.g. 'Whitelist' / 'Blacklist')."""
    params: dict[str, Any] = {}
    if exc_id is not None:
        params["exc_id"] = exc_id
    if scope is not None:
        params["scope"] = scope
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/exceptions/{exc_type}", params=params or None)


async def exceptions_get(
    settings: Settings,
    exc_type: str,
    exc_id: str,
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Get a single exception by type and ID."""
    async with acquire_client(settings, client) as c:
        return await c.get(
            f"/v1.0/exceptions/{exc_type}/{exc_id}", params=_scope_params(scope)
        )


async def exceptions_create(
    settings: Settings,
    exc_type: str,
    fields: dict[str, Any],
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Create an exception. `fields` holds the documented body fields (senderEmail,
    senderDomain, attachmentMd5, subject, comment, actionNeeded, matching flags, etc.)."""
    async with acquire_client(settings, client) as c:
        return await c.post(
            f"/v1.0/exceptions/{exc_type}",
            json={"requestData": fields},
            params=_scope_params(scope),
        )


async def exceptions_update(
    settings: Settings,
    exc_type: str,
    exc_id: str,
    fields: dict[str, Any],
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Update an existing exception by type and ID."""
    async with acquire_client(settings, client) as c:
        return await c.put(
            f"/v1.0/exceptions/{exc_type}/{exc_id}",
            json={"requestData": fields},
            params=_scope_params(scope),
        )


async def exceptions_delete(
    settings: Settings,
    exc_type: str,
    exc_id: str,
    scope: str | None = None,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Delete an exception by type and ID."""
    async with acquire_client(settings, client) as c:
        return await c.post(
            f"/v1.0/exceptions/{exc_type}/delete/{exc_id}", params=_scope_params(scope)
        )


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="exceptions_list")
    async def _exceptions_list(
        exc_type: str, exc_id: str | None = None, scope: str | None = None
    ) -> dict[str, Any]:
        """List exceptions of a given type (e.g. 'Whitelist' / 'Blacklist')."""
        return await exceptions_list(settings, exc_type, exc_id, scope, client=client)

    @app.tool(name="exceptions_get")
    async def _exceptions_get(
        exc_type: str, exc_id: str, scope: str | None = None
    ) -> dict[str, Any]:
        """Get a single exception by type and ID."""
        return await exceptions_get(settings, exc_type, exc_id, scope, client=client)

    @app.tool(name="exceptions_create")
    async def _exceptions_create(
        exc_type: str, fields: dict[str, Any], scope: str | None = None
    ) -> dict[str, Any]:
        """Create an exception. fields holds body fields (senderEmail, senderDomain,
        attachmentMd5, subject, comment, actionNeeded, matching flags, etc.)."""
        return await exceptions_create(settings, exc_type, fields, scope, client=client)

    @app.tool(name="exceptions_update")
    async def _exceptions_update(
        exc_type: str, exc_id: str, fields: dict[str, Any], scope: str | None = None
    ) -> dict[str, Any]:
        """Update an existing exception by type and ID."""
        return await exceptions_update(settings, exc_type, exc_id, fields, scope, client=client)

    @app.tool(name="exceptions_delete")
    async def _exceptions_delete(
        exc_type: str, exc_id: str, scope: str | None = None
    ) -> dict[str, Any]:
        """Delete an exception by type and ID."""
        return await exceptions_delete(settings, exc_type, exc_id, scope, client=client)
