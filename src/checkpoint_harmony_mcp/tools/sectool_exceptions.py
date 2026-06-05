from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ..errors import HarmonyError
from ._common import acquire_client

_URLREP_TYPES = ("allow-url", "allow-domain", "block-url", "block-domain")
_DLP_TYPES = ("hash", "text_content", "sender_email", "recipient_email")


def _validate_type(family: str, exception_type: str, allowed: tuple[str, ...]) -> None:
    if exception_type not in allowed:
        raise HarmonyError(
            f"{family} exception_type must be one of: " + ", ".join(allowed)
        )


# -- URL Reputation (/v1.0/sectool-exceptions/avanan_url) --

async def urlrep_list(
    settings: Settings, exception_type: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """List URL-reputation exceptions for one type
    (allow-url | allow-domain | block-url | block-domain)."""
    _validate_type("urlrep", exception_type, _URLREP_TYPES)
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/sectool-exceptions/avanan_url/exceptions/{exception_type}")


async def urlrep_get(
    settings: Settings, exception_type: str, exception_str: str,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Get a single URL-reputation exception."""
    _validate_type("urlrep", exception_type, _URLREP_TYPES)
    async with acquire_client(settings, client) as c:
        return await c.get(
            f"/v1.0/sectool-exceptions/avanan_url/exceptions/{exception_type}/{exception_str}"
        )


async def urlrep_create(
    settings: Settings, exception_type: str, fields: dict[str, Any],
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Create a URL-reputation exception. ``fields`` must include ``exception_str``;
    may include ``comment``, ``entity_type``, ``entity_id``, ``file_name``,
    ``created_by_email``, ``is_exclusive``."""
    _validate_type("urlrep", exception_type, _URLREP_TYPES)
    request_data = {"exception_type": exception_type, **fields}
    async with acquire_client(settings, client) as c:
        return await c.post(
            "/v1.0/sectool-exceptions/avanan_url",
            json={"requestData": request_data},
            bucket="exceptions_other",
        )


async def urlrep_update(
    settings: Settings, exception_type: str, fields: dict[str, Any],
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Update a URL-reputation exception. ``fields`` must include ``exception_str`` and
    may include ``exception_payload`` (the conditions to overwrite)."""
    _validate_type("urlrep", exception_type, _URLREP_TYPES)
    request_data = {"exception_type": exception_type, **fields}
    async with acquire_client(settings, client) as c:
        return await c.put(
            "/v1.0/sectool-exceptions/avanan_url",
            json={"requestData": request_data},
            bucket="exceptions_other",
        )


async def urlrep_delete(
    settings: Settings, exception_type: str, exception_str: str,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Delete one URL-reputation exception by (type, str)."""
    _validate_type("urlrep", exception_type, _URLREP_TYPES)
    async with acquire_client(settings, client) as c:
        return await c.post(
            "/v1.0/sectool-exceptions/avanan_url/exceptions",
            json={"requestData": {"exception_type": exception_type, "exception_str": exception_str}},
            bucket="exceptions_other",
        )


# -- DLP (/v1.0/sectool-exceptions/avanan_dlp) --

async def dlp_list(
    settings: Settings, exception_type: str, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """List DLP exceptions for one type
    (hash | text_content | sender_email | recipient_email)."""
    _validate_type("dlp", exception_type, _DLP_TYPES)
    async with acquire_client(settings, client) as c:
        return await c.get(f"/v1.0/sectool-exceptions/avanan_dlp/exceptions/{exception_type}")


async def dlp_get(
    settings: Settings, exception_type: str, exception_str: str,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Get a single DLP exception."""
    _validate_type("dlp", exception_type, _DLP_TYPES)
    async with acquire_client(settings, client) as c:
        return await c.get(
            f"/v1.0/sectool-exceptions/avanan_dlp/exceptions/{exception_type}/{exception_str}"
        )


async def dlp_create(
    settings: Settings, exception_type: str, fields: dict[str, Any],
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Create a DLP exception. ``fields`` must include ``exception_str``."""
    _validate_type("dlp", exception_type, _DLP_TYPES)
    request_data = {"exception_type": exception_type, **fields}
    async with acquire_client(settings, client) as c:
        return await c.post(
            "/v1.0/sectool-exceptions/avanan_dlp",
            json={"requestData": request_data},
            bucket="exceptions_other",
        )


async def dlp_update(
    settings: Settings, exception_type: str, fields: dict[str, Any],
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Update a DLP exception. ``fields`` must include ``exception_str`` and may
    include ``exception_payload`` (the conditions to overwrite)."""
    _validate_type("dlp", exception_type, _DLP_TYPES)
    request_data = {"exception_type": exception_type, **fields}
    async with acquire_client(settings, client) as c:
        return await c.put(
            "/v1.0/sectool-exceptions/avanan_dlp",
            json={"requestData": request_data},
            bucket="exceptions_other",
        )


async def dlp_delete(
    settings: Settings, exception_type: str, exception_str: str,
    client: HarmonyClient | None = None,
) -> dict[str, Any]:
    """Delete one DLP exception by (type, str)."""
    _validate_type("dlp", exception_type, _DLP_TYPES)
    async with acquire_client(settings, client) as c:
        return await c.post(
            "/v1.0/sectool-exceptions/avanan_dlp/exceptions",
            json={"requestData": {"exception_type": exception_type, "exception_str": exception_str}},
            bucket="exceptions_other",
        )


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    # URL Reputation
    @app.tool(name="urlrep_list")
    async def _u_list(exception_type: str) -> dict[str, Any]:
        """List URL-reputation exceptions for one type
        (allow-url | allow-domain | block-url | block-domain)."""
        return await urlrep_list(settings, exception_type, client=client)

    @app.tool(name="urlrep_get")
    async def _u_get(exception_type: str, exception_str: str) -> dict[str, Any]:
        """Get a single URL-reputation exception."""
        return await urlrep_get(settings, exception_type, exception_str, client=client)

    @app.tool(name="urlrep_create")
    async def _u_create(exception_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Create a URL-reputation exception. fields must include exception_str."""
        return await urlrep_create(settings, exception_type, fields, client=client)

    @app.tool(name="urlrep_update")
    async def _u_update(exception_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update a URL-reputation exception. fields must include exception_str."""
        return await urlrep_update(settings, exception_type, fields, client=client)

    @app.tool(name="urlrep_delete")
    async def _u_delete(exception_type: str, exception_str: str) -> dict[str, Any]:
        """Delete one URL-reputation exception by (type, str)."""
        return await urlrep_delete(settings, exception_type, exception_str, client=client)

    # DLP
    @app.tool(name="dlp_list")
    async def _d_list(exception_type: str) -> dict[str, Any]:
        """List DLP exceptions for one type
        (hash | text_content | sender_email | recipient_email)."""
        return await dlp_list(settings, exception_type, client=client)

    @app.tool(name="dlp_get")
    async def _d_get(exception_type: str, exception_str: str) -> dict[str, Any]:
        """Get a single DLP exception."""
        return await dlp_get(settings, exception_type, exception_str, client=client)

    @app.tool(name="dlp_create")
    async def _d_create(exception_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Create a DLP exception. fields must include exception_str."""
        return await dlp_create(settings, exception_type, fields, client=client)

    @app.tool(name="dlp_update")
    async def _d_update(exception_type: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update a DLP exception. fields must include exception_str."""
        return await dlp_update(settings, exception_type, fields, client=client)

    @app.tool(name="dlp_delete")
    async def _d_delete(exception_type: str, exception_str: str) -> dict[str, Any]:
        """Delete one DLP exception by (type, str)."""
        return await dlp_delete(settings, exception_type, exception_str, client=client)
