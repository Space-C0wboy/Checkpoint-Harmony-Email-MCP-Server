import json
import re
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


_ENTITY_TOKEN = re.compile(r"#(\{.*?\})", re.DOTALL)


def clean_description(text):
    """Replace Harmony embedded-entity tokens (``#{...json...}``) with their human
    label, leaving surrounding text intact. Non-strings / token-free text pass through."""
    if not isinstance(text, str) or "#{" not in text:
        return text

    def _repl(m: "re.Match[str]") -> str:
        try:
            obj = json.loads(m.group(1))
        except Exception:
            return ""
        return str(obj.get("label") or obj.get("display") or "")

    return _ENTITY_TOKEN.sub(_repl, text)


def _cmp(actual: Any, expected: str, mode: str) -> bool:
    e = (expected or "").lower()
    if mode == "exact":
        return isinstance(actual, str) and actual.lower() == e
    if mode == "contains":
        return isinstance(actual, str) and e in actual.lower()
    if mode == "in":
        return isinstance(actual, list) and any(isinstance(x, str) and x.lower() == e for x in actual)
    return False


def record_matches(comparisons: "list[tuple[Any, str, str]]") -> bool:
    """AND of (actual, expected, mode) comparisons. mode in {'exact','contains','in'};
    all case-insensitive. Caller includes only the filters that were provided."""
    return all(_cmp(actual, expected, mode) for actual, expected, mode in comparisons)


def normalize_task_status(task_json: dict[str, Any]) -> dict[str, Any]:
    """Derive a reliable task status from the inner per-action statuses (the outer
    ``status`` lags). Returns {status, message, actions, raw}."""
    actions = (task_json.get("responseData") or {}).get("actions") or []
    statuses = [a.get("action_status") for a in actions]
    if any(s == "failed" for s in statuses):
        status = "failed"
    elif actions and all(s == "completed" for s in statuses):
        status = "completed"
    else:
        status = "inprogress"
    inner = [{"name": a.get("action_name"), "status": a.get("action_status"), "message": a.get("action_message")} for a in actions]
    message = "; ".join(filter(None, (a.get("action_message") for a in actions)))
    return {"status": status, "message": message, "actions": inner, "raw": task_json}
