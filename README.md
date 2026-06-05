# Check Point Harmony Email & Collaboration MCP Server

An MCP server exposing the Check Point Harmony Email & Collaboration smart-api
(formerly Avanan): Security Events, Secured Entities, Exceptions, and Scopes.
15 tools, full endpoint parity with the v1.50 API.

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `CHECKPOINT_CLIENT_ID` | yes | Infinity Portal API key Client ID |
| `CHECKPOINT_SECRET` | yes | Infinity Portal API key Secret (accessKey) |
| `CHECKPOINT_AUTH_URL` | yes | Region gateway + `/auth/external` |
| `CHECKPOINT_API_URL` | yes | Region gateway + `/app/hec-api` |
| `CHECKPOINT_SCOPE` | no* | Auto-discovered when blank (single tenant); set explicitly only for multi-scope keys |
| `CHECKPOINT_TIMEOUT` | no | Request timeout, default 30 |
| `LOG_LEVEL` | no | default INFO |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | no | HTTP transport bind, defaults 127.0.0.1:8765 |

\* Optional: when blank the server auto-discovers the scope (single-tenant). Set it
explicitly only if your key has access to multiple scopes; discover values via
`scopes_list`.

### Region gateways
- EU `https://cloudinfra-gw.portal.checkpoint.com`
- US `https://cloudinfra-gw-us.portal.checkpoint.com`
- AU `https://cloudinfra-gw.ap.portal.checkpoint.com`
- IN `https://cloudinfra-gw.in.portal.checkpoint.com`

## Install

`./scripts/setup.sh` (or `uv venv && uv pip install -e ".[dev]"`).

## Run

- stdio (default): `uv run checkpoint-harmony-mcp`
- HTTP: `uv run checkpoint-harmony-mcp --transport http --port 8765`

## Use with an MCP client

The server speaks MCP over **stdio**. Point your client at the `uv run` entry
point and pass credentials either via the config's `env` block (shown below) or
a `.env` file in the project directory.

### Claude Desktop

Edit `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "checkpoint-harmony": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/Checkpoint-Harmony-Email-MCP-Server",
        "checkpoint-harmony-mcp"
      ],
      "env": {
        "CHECKPOINT_CLIENT_ID": "your-client-id",
        "CHECKPOINT_SECRET": "your-client-secret",
        "CHECKPOINT_AUTH_URL": "https://cloudinfra-gw-us.portal.checkpoint.com/auth/external",
        "CHECKPOINT_API_URL": "https://cloudinfra-gw-us.portal.checkpoint.com/app/hec-api",
        "CHECKPOINT_SCOPE": "your-scope-id"
      }
    }
  }
}
```

Restart Claude Desktop, then confirm `checkpoint-harmony` appears in the
tools menu. On Windows, use a full path with escaped backslashes for
`--directory` (e.g. `C:\\Users\\you\\source\\repos\\Checkpoint-Harmony-Email-MCP-Server`).

### Claude Code

```bash
claude mcp add checkpoint-harmony \
  --env CHECKPOINT_CLIENT_ID=your-client-id \
  --env CHECKPOINT_SECRET=your-client-secret \
  --env CHECKPOINT_AUTH_URL=https://cloudinfra-gw-us.portal.checkpoint.com/auth/external \
  --env CHECKPOINT_API_URL=https://cloudinfra-gw-us.portal.checkpoint.com/app/hec-api \
  --env CHECKPOINT_SCOPE=your-scope-id \
  -- uv run --directory /absolute/path/to/Checkpoint-Harmony-Email-MCP-Server checkpoint-harmony-mcp
```

Verify with `claude mcp list`. If you keep credentials in a `.env` file in the
project directory, you can drop the `--env` flags.

> Tip: run the `scopes_list` tool first to discover the value for
> `CHECKPOINT_SCOPE`. Until it's set, only `scopes_list` will work.

## Tools

See `docs/ENDPOINTS.md` for the full tool ↔ endpoint mapping.

### Query tools (`events_query`, `entities_query`)

- `events_query` **requires a date range** — include `startDate` (and usually
  `endDate`) in `filters`, or the API returns a 500.
- Both query tools return a **compact summary of up to `limit` records (default 25)**
  to stay chat-friendly. Pass `full=true` for complete objects, and use the response
  envelope's `scrollId` to page for more.
- `events_query`/`entities_query` accept `max_records` (auto-paginate, cap 500; sets
  `truncated: true` if more remain) and `count_only` (returns `{recordsNumber, histogram}`).
- Use `events_find` / `entities_find` to locate a specific message/event by sender,
  recipient, subject, message-ID, or entity-ID within a date window.
- `events_action` / `entities_action` **wait for completion by default** and return the
  final state; pass `wait=false` for fire-and-forget. `exc_type` is case-insensitive.

## Development

`uv run pytest` runs the full suite (HTTP fully mocked with `respx`; no live calls).
`uv run ruff check .` lints.

## License

[MIT](LICENSE)
