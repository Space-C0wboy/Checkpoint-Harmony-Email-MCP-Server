from typing import Any

from ..client import HarmonyClient
from ..config import Settings


async def scopes_list(settings: Settings) -> dict[str, Any]:
    """List the scopes (portals/customers) available to these API credentials."""
    async with HarmonyClient(settings) as client:
        return await client.get("/v1.0/scopes")


def register(app, settings: Settings) -> None:
    @app.tool(name="scopes_list")
    async def _scopes_list() -> dict[str, Any]:
        """List the scopes (portals/customers) available to these API credentials."""
        return await scopes_list(settings)
