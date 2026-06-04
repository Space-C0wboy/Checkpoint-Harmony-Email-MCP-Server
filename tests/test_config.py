import pytest
from checkpoint_harmony_mcp.config import Settings


def _kwargs(**over):
    base = dict(
        checkpoint_client_id="cid",
        checkpoint_secret="sec",
        checkpoint_auth_url="https://gw.example/auth/external",
        checkpoint_api_url="https://gw.example/app/hec-api",
    )
    base.update(over)
    return base


def test_settings_loads_required_fields():
    s = Settings(**_kwargs())
    assert s.checkpoint_client_id == "cid"
    assert s.checkpoint_timeout == 30
    assert s.mcp_http_port == 8765
    assert s.checkpoint_scope == ""


def test_settings_strips_trailing_slash_on_urls():
    s = Settings(**_kwargs(checkpoint_api_url="https://gw.example/app/hec-api/"))
    assert s.checkpoint_api_url == "https://gw.example/app/hec-api"


def test_settings_missing_required_raises():
    with pytest.raises(Exception):
        Settings(checkpoint_client_id="cid")
