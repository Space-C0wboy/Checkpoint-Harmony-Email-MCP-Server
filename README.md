# Check Point Harmony Email & Collaboration MCP Server

An MCP server exposing the Check Point Harmony Email & Collaboration smart-api
(formerly Avanan): Security Events, Secured Entities, Exceptions, and Scopes.
13 tools, full endpoint parity with the v1.50 API.

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `CHECKPOINT_CLIENT_ID` | yes | Infinity Portal API key Client ID |
| `CHECKPOINT_SECRET` | yes | Infinity Portal API key Secret (accessKey) |
| `CHECKPOINT_AUTH_URL` | yes | Region gateway + `/auth/external` |
| `CHECKPOINT_API_URL` | yes | Region gateway + `/app/hec-api` |
| `CHECKPOINT_SCOPE` | yes* | Scope sent on every API call; discover via `scopes_list` |
| `CHECKPOINT_TIMEOUT` | no | Request timeout, default 30 |
| `LOG_LEVEL` | no | default INFO |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | no | HTTP transport bind, defaults 127.0.0.1:8765 |

\* The API requires the `scopes` header on every call. Leave blank only to call
`scopes_list` for discovery.

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

## Tools

See `docs/ENDPOINTS.md` for the full tool ↔ endpoint mapping.

## Development

`uv run pytest` runs the full suite (HTTP fully mocked with `respx`; no live calls).
`uv run ruff check .` lints.
