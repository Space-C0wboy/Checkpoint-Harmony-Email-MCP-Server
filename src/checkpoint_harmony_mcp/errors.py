class HarmonyError(Exception):
    """Base error for the Harmony MCP server."""


class AuthError(HarmonyError):
    """Authentication or token-refresh failure."""


class ApiError(HarmonyError):
    """Non-2xx API response."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(ApiError):
    """429 Too Many Requests after backoff."""
