from checkpoint_harmony_mcp import server

EXPECTED_TOOLS = {
    "scopes_list",
    "events_get_by_id", "events_query", "events_action", "events_get_task_status",
    "entities_get_by_id", "entities_query", "entities_action",
    "exceptions_list", "exceptions_get", "exceptions_create",
    "exceptions_update", "exceptions_delete",
    "events_find", "entities_find",
    "entities_download",
    "urlrep_list", "urlrep_get", "urlrep_create", "urlrep_update", "urlrep_delete",
    "dlp_list", "dlp_get", "dlp_create", "dlp_update", "dlp_delete",
}


def _env(monkeypatch):
    monkeypatch.setenv("CHECKPOINT_CLIENT_ID", "cid")
    monkeypatch.setenv("CHECKPOINT_SECRET", "sec")
    monkeypatch.setenv("CHECKPOINT_AUTH_URL", "https://gw.example/auth/external")
    monkeypatch.setenv("CHECKPOINT_API_URL", "https://gw.example/app/hec-api")
    monkeypatch.setenv("CHECKPOINT_SCOPE", "scope-1")


def test_build_server_returns_fastmcp(monkeypatch):
    _env(monkeypatch)
    app = server.build_server()
    assert app is not None
    assert app.name == "checkpoint-harmony"


async def test_all_tools_registered(monkeypatch):
    _env(monkeypatch)
    app = server.build_server()
    names = {t.name for t in await app.list_tools()}
    assert names == EXPECTED_TOOLS
