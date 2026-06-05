# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
