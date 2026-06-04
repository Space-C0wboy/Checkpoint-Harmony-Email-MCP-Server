from checkpoint_harmony_mcp.errors import (
    HarmonyError, AuthError, ApiError, RateLimitError,
)


def test_error_hierarchy():
    assert issubclass(AuthError, HarmonyError)
    assert issubclass(ApiError, HarmonyError)
    assert issubclass(RateLimitError, ApiError)


def test_api_error_carries_status_and_message():
    e = ApiError("boom", status_code=500)
    assert e.status_code == 500
    assert "boom" in str(e)
