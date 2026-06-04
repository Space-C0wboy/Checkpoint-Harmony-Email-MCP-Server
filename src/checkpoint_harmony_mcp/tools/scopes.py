from typing import Any

from ..client import HarmonyClient
from ..config import Settings
from ._common import acquire_client


async def scopes_list(
    settings: Settings, client: HarmonyClient | None = None
) -> dict[str, Any]:
    """List the scopes (portals/customers) available to these API credentials."""
    async with acquire_client(settings, client) as c:
        return await c.get("/v1.0/scopes")


def register(app, settings: Settings, client: HarmonyClient | None = None) -> None:
    @app.tool(name="scopes_list")
    async def _scopes_list() -> dict[str, Any]:
        """List the scopes (portals/customers) available to these API credentials."""
        return await scopes_list(settings, client=client)
