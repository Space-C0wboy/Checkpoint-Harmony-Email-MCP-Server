from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

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


def apply_view(
    resp: dict[str, Any],
    limit: int,
    full: bool,
    compactor: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Trim ``responseData`` to ``limit`` records and, unless ``full``, map each
    record through ``compactor``. ``responseEnvelope`` and all other keys are
    preserved. Returns ``resp`` unchanged when there is no non-empty list under
    ``responseData``. Does not mutate the input.
    """
    data = resp.get("responseData")
    if not isinstance(data, list) or not data:
        return resp
    # Clamp to avoid negative-index surprises (e.g. limit=-1 dropping the last record).
    sliced = data[: max(limit, 0)]
    new_data = sliced if full else [compactor(r) for r in sliced]
    return {**resp, "responseData": new_data}
