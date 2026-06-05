# Check Point Harmony Email & Collaboration MCP Server

[![PyPI version](https://img.shields.io/pypi/v/checkpoint-harmony-mcp.svg)](https://pypi.org/project/checkpoint-harmony-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/checkpoint-harmony-mcp.svg)](https://pypi.org/project/checkpoint-harmony-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/actions/workflows/ci.yml/badge.svg)](https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/actions/workflows/ci.yml)

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
Check Point **Harmony Email & Collaboration** smart-api (formerly Avanan) to AI
assistants. It provides **15 tools** across Security Events, Secured Entities,
Exceptions, and Scopes — full parity with the v1.50 API.

> **Unofficial / community project.** Not affiliated with, endorsed by, or supported by
> Check Point Software Technologies. "Check Point", "Harmony", and "Avanan" are
> trademarks of their respective owner.

## Important notices

> **Beta software.** APIs and tool shapes may change. Validate against a non-production
> scope before relying on it.

> **Destructive capabilities.** `events_action` and `entities_action` **quarantine and
> restore real email**, and the `exceptions_*` tools **modify allow/block lists**. An AI
> assistant invoking these changes your live mail flow.

Recommended security posture:

- Test against a lab / non-production scope before using it on production mail.
- Treat the Client ID and Secret like passwords — never commit `.env`; prefer per-call
  scoping where possible.
- Review any state-changing action (quarantine, restore, block, allow) before approving it.
- Keep the HTTP transport bound to localhost (the default) — do not expose it to a network.

## Tools

| Area | Count | Tools |
|------|-------|-------|
| Scopes | 1 | `scopes_list` |
| Security Events | 5 | `events_get_by_id`, `events_query`, `events_find`, `events_action`, `events_get_task_status` |
| Secured Entities | 4 | `entities_get_by_id`, `entities_query`, `entities_find`, `entities_action` |
| Exceptions | 5 | `exceptions_list`, `exceptions_get`, `exceptions_create`, `exceptions_update`, `exceptions_delete` |

**15 tools total.** Highlights:

- **Query tools** (`events_query`, `entities_query`) return a compact summary of up to
  `limit` records (default 25). Use `max_records` (cap 500) to auto-paginate, `count_only`
  for a `{recordsNumber, histogram}` triage view, or `full=true` for raw objects.
  `events_query` requires a date range (`startDate`).
- **Find tools** (`events_find`, `entities_find`) locate a specific message/event by
  sender, recipient, subject, message-ID, or entity-ID within a date window.
- **Action tools** (`events_action`, `entities_action`) wait for completion by default and
  return the final entity state; pass `wait=false` for fire-and-forget.

See [`docs/ENDPOINTS.md`](docs/ENDPOINTS.md) for the full tool ↔ endpoint mapping.

## Quick start

### Install

```bash
# with uv (recommended)
uv tool install checkpoint-harmony-mcp

# or with pip
pip install checkpoint-harmony-mcp
```

For development from source:

```bash
git clone https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server
cd Checkpoint-Harmony-Email-MCP-Server
uv venv && uv pip install -e ".[dev]"
```

### Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `CHECKPOINT_CLIENT_ID` | yes | Infinity Portal API key Client ID |
| `CHECKPOINT_SECRET` | yes | Infinity Portal API key Secret (accessKey) |
| `CHECKPOINT_AUTH_URL` | yes | Region gateway + `/auth/external` |
| `CHECKPOINT_API_URL` | yes | Region gateway + `/app/hec-api` |
| `CHECKPOINT_SCOPE` | no* | Auto-discovered when blank (single tenant); set explicitly only for multi-scope keys |
| `CHECKPOINT_TIMEOUT` | no | Request timeout in seconds (default 30) |
| `LOG_LEVEL` | no | default `INFO` |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | no | HTTP transport bind, defaults `127.0.0.1:8765` |

\* When blank, the server auto-discovers the scope (single-tenant). Set it explicitly only
if your key has access to multiple scopes; discover values with the `scopes_list` tool.

**Region gateways:**

- EU `https://cloudinfra-gw.portal.checkpoint.com`
- US `https://cloudinfra-gw-us.portal.checkpoint.com`
- AU `https://cloudinfra-gw.ap.portal.checkpoint.com`
- IN `https://cloudinfra-gw.in.portal.checkpoint.com`

(Auth URL = gateway + `/auth/external`; API URL = gateway + `/app/hec-api`.)

### Run

- stdio (default): `uv run checkpoint-harmony-mcp` (or just `checkpoint-harmony-mcp` if installed as a tool)
- HTTP: `checkpoint-harmony-mcp --transport http --port 8765`

## Editor integration

### Claude Desktop

Edit `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "checkpoint-harmony": {
      "command": "checkpoint-harmony-mcp",
      "env": {
        "CHECKPOINT_CLIENT_ID": "your-client-id",
        "CHECKPOINT_SECRET": "your-client-secret",
        "CHECKPOINT_AUTH_URL": "https://cloudinfra-gw-us.portal.checkpoint.com/auth/external",
        "CHECKPOINT_API_URL": "https://cloudinfra-gw-us.portal.checkpoint.com/app/hec-api"
      }
    }
  }
}
```

If running from source instead of an installed tool, use `uv` with `--directory`:

```json
{
  "mcpServers": {
    "checkpoint-harmony": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Checkpoint-Harmony-Email-MCP-Server", "checkpoint-harmony-mcp"],
      "env": { "CHECKPOINT_CLIENT_ID": "...", "CHECKPOINT_SECRET": "...", "CHECKPOINT_AUTH_URL": "...", "CHECKPOINT_API_URL": "..." }
    }
  }
}
```

Restart Claude Desktop, then confirm `checkpoint-harmony` appears in the tools menu.

### Claude Code

```bash
claude mcp add checkpoint-harmony \
  --env CHECKPOINT_CLIENT_ID=your-client-id \
  --env CHECKPOINT_SECRET=your-client-secret \
  --env CHECKPOINT_AUTH_URL=https://cloudinfra-gw-us.portal.checkpoint.com/auth/external \
  --env CHECKPOINT_API_URL=https://cloudinfra-gw-us.portal.checkpoint.com/app/hec-api \
  -- checkpoint-harmony-mcp
```

## Scope auto-discovery

The Harmony API requires a `scopes` value on every call, but it isn't shown in the
Infinity Portal. This server resolves it for you: leave `CHECKPOINT_SCOPE` **blank** and,
on first use, it calls `scopes_list` and uses your single scope automatically (logging it
so you can pin it later). Set `CHECKPOINT_SCOPE` explicitly only if your key spans
multiple scopes — the server will list the available values in an error if so.

## Example prompts

- *"How many phishing emails did we get today?"* → `events_query` with `count_only`.
- *"Find the email from `scdc205@proton.me` to me on June 4th."* → `entities_find`.
- *"Quarantine event `<id>`, then restore it."* → `events_action` (quarantine → restore).
- *"Block the sender `bad@example.com`."* / *"Remove that block."* → `exceptions_create` / `exceptions_delete`.
- *"Show me the full detail for entity `<id>`."* → `entities_get_by_id`.

## Development

```bash
uv run pytest        # full suite (HTTP fully mocked with respx; no live calls)
uv run ruff check .  # lint
```

Releases publish to PyPI automatically when a `v*` tag is pushed (see
`.github/workflows/publish.yml`).

## License

[MIT](LICENSE)
