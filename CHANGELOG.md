# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2026-06-06

First published release on PyPI. No functional changes to the MCP tools since 0.2.3 —
this release covers packaging and repository hardening.

### Changed
- CI installs dependencies via `uv sync` + runs through `uv run`, replacing a
  `uv pip install --system` step that failed on the runner's externally-managed
  system Python (PEP 668).
- The publish workflow now verifies the pushed tag matches the `pyproject.toml` version
  and runs `twine check` on the built artifacts before uploading.

### Removed
- Internal development docs (design specs and plans) and the vendored OpenAPI spec are no
  longer tracked in the repository.

[0.2.4]: https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/releases/tag/v0.2.4

## [0.2.3] - 2026-06-06

### Changed
- `events_find` now caps results to a `limit` (default 25), stopping the page scan early
  once enough matches are collected, and returns a `truncated` flag (`true` when the limit
  or the page-scan cap was hit). This prevents oversized responses when a sender matches
  thousands of events. `entities_find` was already capped.

[0.2.3]: https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/releases/tag/v0.2.3

## [0.2.2] - 2026-06-06

### Changed
- `entities_find` and `events_find` now filter **server-side** and default to the **last
  30 days** when `start_date` is omitted. Matching tries exact first and falls back to
  contains, reported via a new `matchMode` field (`exact` | `contains` | `none`).
  `entities_find` uses precise `entityExtendedFilter` operators and no longer returns
  `pagesScanned`/`scanCapHit`; `events_find` narrows via the `description` filter (or
  `eventIds` for `event_id`) and retains `pagesScanned`/`scanCapHit`. `entities_find`
  also gains `limit`/`max_records` and an `entity_id` direct-lookup short-circuit.

### Fixed
- `entities_query`'s `extended_filter` is now a properly-typed array, so MCP clients
  serialize it as JSON instead of a rejected string; it also accepts a JSON string
  defensively. Server-side entity filtering is now usable directly.

[0.2.2]: https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/releases/tag/v0.2.2

## [0.2.1] - 2026-06-06

### Fixed
- Reverted a v0.2.0 regression that sent `events_action`/`entities_action` action names
  and params as JSON arrays and dropped the required `entityType` field, which caused the
  live API to reject quarantine/restore. Action bodies now use scalar enum names and
  scalar params again; `entities_action` again requires `entity_type` (the entity's
  `saasEntityType`, e.g. `office365_emails_email`).
- Corrected `urlrep_delete`/`dlp_delete` to delete exceptions via
  `DELETE /v1.0/sectool-exceptions/{family}/exceptions` with a
  `{requestData: {exception_type, exception_str_list}}` body. The previous
  `POST .../exceptions` call with an `exception_str` field was rejected by the API
  ("Exception is invalid!").

[0.2.1]: https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/releases/tag/v0.2.1

## [0.2.0] - 2026-06-05

### Changed (breaking)
- **Action body wire shape:** `eventActionName`/`entityActionName` and their `…Param`
  fields are now sent as JSON arrays per the API reference. Tool argument signatures
  are unchanged (callers still pass a single string); wrapping happens internally.
- **Removed undocumented body/query fields:** dropped the `entity_type=` kwarg from
  `entities_action`, the `scope=` kwarg from `events_action` / `entities_action` /
  all five `exceptions_*` tools, and the `exc_id=` query plumbing in `exceptions_list`.
  None of these appeared in the API reference. Pass scope via `CHECKPOINT_SCOPE`
  or the `scopes` header — never in the body.
- **Bulk action return shape:** when `events_action`/`entities_action` is called with
  multiple IDs and `wait=True`, it now returns `{tasks: [...], summary: {...}}`
  aggregated across all returned tasks. Single-ID + wait still returns the legacy
  `{taskId, status, finalState, raw}` shape.

### Added
- 10 sectool exception tools across two families: **URL Reputation**
  (`urlrep_list/get/create/update/delete` with types `allow-url`, `allow-domain`,
  `block-url`, `block-domain`) and **DLP** (`dlp_list/get/create/update/delete`
  with types `hash`, `text_content`, `sender_email`, `recipient_email`).
- `entities_download` — fetch a secured-entity message as an `.eml`
  (returns `{filename, contentType, sizeBytes, base64}`).
- Proactive client-side rate limiting per the documented limits: 1 rps for
  Anti-Phishing exception writes; 10 rps for URL-rep + DLP exception writes.
- Documented additional `events_action` verbs (`dismiss`, `severityChange`,
  `senttoadmin`) and the `entityExtendedFilter` operator set
  (`is/contains/startsWith/isEmpty/isNot/notContains/isNotEmpty/greaterThan/lessThan`).
- `exceptions_*` tools now accept `spam_whitelist` alongside `whitelist`/`blacklist`.

### Fixed
- Scope auto-discovery: multiple discovered scopes are now joined with commas (per
  the API reference) instead of raising. Multi-scope keys work without manual config.
- Auth: prefer the documented `expiresIn`; if absent, parse the ISO `expires`
  timestamp; if both are absent, fall back to the prior 3600 s default.

[0.2.0]: https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/releases/tag/v0.2.0

## [0.1.0] - 2026-06-05

Initial release.

### Added
- 15 MCP tools across four areas of the Harmony Email & Collaboration smart-api (v1.50):
  - **Scopes:** `scopes_list`.
  - **Security Events:** `events_get_by_id`, `events_query`, `events_find`,
    `events_action`, `events_get_task_status`.
  - **Secured Entities:** `entities_get_by_id`, `entities_query`, `entities_find`,
    `entities_action`.
  - **Exceptions:** `exceptions_list`, `exceptions_get`, `exceptions_create`,
    `exceptions_update`, `exceptions_delete`.
- Client-credentials auth with token caching/refresh and **automatic scope discovery**
  (optional `CHECKPOINT_SCOPE`).
- Chat-friendly query output: compact summaries, `limit`, `max_records` auto-pagination
  (cap 500), `count_only` histograms, and `full` raw mode.
- `*_find` tools for locating a specific message/event by sender, recipient, subject,
  message-ID, or entity-ID.
- Action tools that wait for task completion by default and return the final entity state;
  normalized task status.
- stdio and HTTP transports; `respx`-mocked test suite; CI on push/PR.

[0.1.0]: https://github.com/Space-C0wboy/Checkpoint-Harmony-Email-MCP-Server/releases/tag/v0.1.0
