from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ._common import acquire_client


def _norm_type(exc_type: str) -> str:
    return exc_type.strip().lower()


async def exceptions_list(
    settings: Settings, exc_type: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """List exceptions of a given type. Accepted types (case-insensitive):
    'whitelist', 'blacklist', 'spam_whitelist'."""
    exc_type = _norm_type(exc_type)
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/exceptions/{exc_type}")


async def exceptions_get(
    settings: Settings, exc_type: str, exc_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Get a single exception by type and ID."""
    exc_type = _norm_type(exc_type)
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/exceptions/{exc_type}/{exc_id}")


async def exceptions_create(
    settings: Settings,
    exc_type: str,
    fields: dict[str, Any],
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Create an exception. `fields` are the documented body fields (senderEmail,
    senderDomain, attachmentMd5, subject, comment, actionNeeded, matching flags, etc.).
    Accepted types (case-insensitive): 'whitelist', 'blacklist', 'spam_whitelist'."""
    exc_type = _norm_type(exc_type)
    async with acquire_client(settings, client) as c:
        return await c.post(
            f"/v1.0/exceptions/{exc_type}",
            json={"requestData": fields},
            bucket="exceptions_ap",
        )


async def exceptions_update(
    settings: Settings,
    exc_type: str,
    exc_id: str,
    fields: dict[str, Any],
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Update an existing exception by type and ID."""
    exc_type = _norm_type(exc_type)
    async with acquire_client(settings, client) as c:
        return await c.put(
            f"/v1.0/exceptions/{exc_type}/{exc_id}",
            json={"requestData": fields},
            bucket="exceptions_ap",
        )


async def exceptions_delete(
    settings: Settings, exc_type: str, exc_id: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """Delete an exception by type and ID."""
    exc_type = _norm_type(exc_type)
    async with acquire_client(settings, client) as c:
        return await c.post(
            f"/v1.0/exceptions/{exc_type}/delete/{exc_id}",
            bucket="exceptions_ap",
        )


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="exceptions_list")
    async def _exceptions_list(exc_type: str) -> dict[str, Any]:
        """List exceptions of a given type ('whitelist'/'blacklist'/'spam_whitelist',
        case-insensitive)."""
        return await exceptions_list(settings, exc_type, client=client)

    @app.tool(name="exceptions_get")
    async def _exceptions_get(exc_type: str, exc_id: str) -> dict[str, Any]:
        """Get a single exception by type and ID."""
        return await exceptions_get(settings, exc_type, exc_id, client=client)

    @app.tool(name="exceptions_create")
    async def _exceptions_create(exc_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Create an exception. fields holds body fields (senderEmail, senderDomain,
        attachmentMd5, subject, comment, actionNeeded, matching flags, etc.). Types
        (case-insensitive): whitelist, blacklist, spam_whitelist."""
        return await exceptions_create(settings, exc_type, fields, client=client)

    @app.tool(name="exceptions_update")
    async def _exceptions_update(
        exc_type: str, exc_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing exception by type and ID."""
        return await exceptions_update(settings, exc_type, exc_id, fields, client=client)

    @app.tool(name="exceptions_delete")
    async def _exceptions_delete(exc_type: str, exc_id: str) -> dict[str, Any]:
        """Delete an exception by type and ID."""
        return await exceptions_delete(settings, exc_type, exc_id, client=client)
