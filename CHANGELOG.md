# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
