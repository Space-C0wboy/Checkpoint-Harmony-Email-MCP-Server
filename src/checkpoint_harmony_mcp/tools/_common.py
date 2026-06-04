from contextlib import asynccontextmanager
from typing import AsyncIterator

from ..client import HarmonyClient
from ..config import Settings


@asynccontextmanager
async def acquire_client(
    settings: Settings, client: HarmonyClient | None
) -> AsyncIterator[HarmonyClient]:
    """Yield a shared client if provided, else a short-lived one bound to settings.

    A provided (shared) client is NOT closed here -- its lifetime is owned by the
    caller (the server). A short-lived client is opened and closed per call.
    """
    if client is not None:
        yield client
    else:
        async with HarmonyClient(settings) as owned:
            yield owned
