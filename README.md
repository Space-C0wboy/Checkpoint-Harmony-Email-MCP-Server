# Check Point Harmony Email & Collaboration MCP Server

[![PyPI version](https://img.shields.io/pypi/v/checkpoint-harmony-mcp.svg)](https://pypi.org/project/checkpoint-harmony-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/checkpoint-harmony-mcp.svg)](https://pypi.org/project/checkpoint-harmony-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/actions/workflows/ci.yml/badge.svg)](https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/actions/workflows/ci.yml)

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
Check Point **Harmony Email & Collaboration** smart-api (formerly Avanan) to AI
assistants. It provides **26 tools** across Security Events, Secured Entities,
Exceptions, URL Reputation, DLP, and Scopes — full parity with the v1.50 API.

> [!IMPORTANT]
> **Unofficial project.** This is an independent, community-built MCP server developed
> against Check Point's published API documentation. It is **not** an official Check Point
> product and is not affiliated with, endorsed by, or supported by Check Point Software
> Technologies. "Check Point", "Harmony", and "Avanan" are trademarks of Check Point
> Software Technologies. For official support of the Harmony Email & Collaboration platform
> itself, contact Check Point directly.

> [!WARNING]
> **Beta software — not yet recommended for production environments.** This project is
> under active development. The tool surface and individual tool body shapes may still
> change between minor versions, and not every endpoint has been exhaustively exercised
> against every tenant configuration. Use against a lab or non-production scope until
> you're confident in the behavior for your use case.
>
> **This server can also perform destructive actions against your Harmony environment.**
> Tools can quarantine and restore real email and modify allow/block-list exceptions. A
> hallucinated tool argument from your AI assistant could alter your mail flow in ways
> that affect email security.
>
> **Recommended posture:**
> - Try the server against a non-production or lab scope first.
> - Use a Check Point API key scoped to the **minimum permissions** your use case requires.
> - Review every destructive tool call before allowing execution. Claude Desktop requires
>   tool-call approval by default — keep that enabled.
> - Treat the API key (Client ID + Secret) with the same care as portal admin credentials,
>   because functionally it is one.
> - The HTTP transport binds to `127.0.0.1` by default. Do not expose it to the public
>   internet without adding authentication.

## Tools

| Area | Count | Tools |
|------|-------|-------|
| Scopes | 1 | `scopes_list` |
| Security Events | 5 | `events_get_by_id`, `events_query`, `events_find`, `events_action`, `events_get_task_status` |
| Secured Entities | 5 | `entities_get_by_id`, `entities_query`, `entities_find`, `entities_action`, `entities_download` |
| Exceptions (Anti-Phishing) | 5 | `exceptions_list`, `exceptions_get`, `exceptions_create`, `exceptions_update`, `exceptions_delete` |
| URL Reputation | 5 | `urlrep_list`, `urlrep_get`, `urlrep_create`, `urlrep_update`, `urlrep_delete` |
| DLP | 5 | `dlp_list`, `dlp_get`, `dlp_create`, `dlp_update`, `dlp_delete` |

**26 tools total.** Highlights:

- **Query tools** (`events_query`, `entities_query`) return a compact summary of up to
  `limit` records (default 25). Use `max_records` (cap 500) to auto-paginate, `count_only`
  for a `{recordsNumber, histogram}` triage view, or `full=true` for raw objects.
  `events_query` requires a date range (`startDate`).
- **Find tools** (`events_find`, `entities_find`) locate a specific message/event by
  sender, recipient, subject, message-ID, or entity-ID. They filter **server-side** and
  default to the **last 30 days** (override with `start_date`/`end_date`), trying an exact
  match first and falling back to `contains` — the result's `matchMode` says which hit.
  Power users can pass a raw server-side `extended_filter` to `entities_query`.
- **Action tools** (`events_action`, `entities_action`) wait for completion by default and
  return the final entity state; pass `wait=false` for fire-and-forget. `entities_action`
  requires `entity_type` — the target entity's `saasEntityType` (e.g.
  `office365_emails_email`), as returned by `entities_query`/`entities_find`.
- **`exceptions_*`** (anti-phishing) types are `whitelist`, `blacklist`, and `spam_whitelist`
  (case-insensitive). **URL-Reputation** exception types are `allow-url`, `allow-domain`,
  `block-url`, `block-domain`. **DLP** exception types are `hash`, `text_content`,
  `sender_email`, `recipient_email`.
- **`entities_download`** returns the secured entity's message as an `.eml`
  (base64-encoded for transport).
- **Rate limits enforced client-side:** Anti-Phishing exception writes are paced to
  **1 rps**; URL-Rep + DLP exception writes to **10 rps**, matching the API reference.
- **`events_action` verbs:** `quarantine`, `restore`, `dismiss`, `severityChange`
  (param `{"newSeverity": "Low|Medium|High|Highest"}`), `senttoadmin`.
- **Server-side filters** for `entities_query` via `extended_filter`: each entry is
  `{saasAttrName, saasAttrOp, saasAttrValue}`; operators are `is`, `contains`,
  `startsWith`, `isEmpty`, `isNot`, `notContains`, `isNotEmpty`, `greaterThan`,
  `lessThan`. Use dotted paths like `entityPayload.fromEmail`.

> [!NOTE]
> `events_query` and `events_find` require a date range — include `startDate` (and ideally
> `endDate`). Without it the upstream API returns an opaque `500`.

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

### Getting an API key

Generate an **account-scoped** Infinity Portal API key for the **Email & Collaboration**
service. The easiest path also shows you the exact authentication URL for your region:

1. In the **Harmony Email & Collaboration** console, confirm the correct **account /
   company** is selected, then click the **Settings** gear next to the company name →
   **API Keys**. (Equivalently: Infinity Portal **Global Settings → API Keys → New
   Account API key**.)
2. Click **New**, choose **Service: Email & Collaboration**, optionally set an expiration,
   then **Create**.
3. Copy the **Client ID**, **Secret Key**, and **Authentication URL** it displays — the
   secret is shown only once. These map to `CHECKPOINT_CLIENT_ID`, `CHECKPOINT_SECRET`,
   and `CHECKPOINT_AUTH_URL`. Set `CHECKPOINT_API_URL` to your region's gateway +
   `/app/hec-api` (see Region gateways below).

No role is requested for Email & Collaboration keys — they are granted Admin access scoped
to that single service.

> [!WARNING]
> Use an **account** API key, not a **user** key. A user-scoped key (the
> `/auth/external/user` endpoint) is bound to the user's home region and is **not** accepted
> by the smart-api — it authenticates successfully but every data call returns an opaque
> `500`. If you decode such a token you'll see `"authType": "EXTERNAL_USER"`; an account key
> shows `"EXTERNAL"`. Always generate the key via *Global Settings → API Keys → New Account
> API key* (or the Harmony console **gear → API Keys**).

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

> [!TIP]
> For a single-tenant key, just leave `CHECKPOINT_SCOPE` unset — there is nothing to look
> up in the portal. Only multi-scope keys need it set explicitly.

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
