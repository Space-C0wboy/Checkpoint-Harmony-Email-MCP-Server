# Harmony Email & Collaboration — Endpoint Inventory

Tool ↔ endpoint mapping for the Harmony Email & Collaboration smart-api (v1.50). All
paths are relative to `CHECKPOINT_API_URL` (region gateway + `/app/hec-api`).
`POST /auth/external` is handled internally by the TokenManager and is not a tool.

| Module        | Tool                     | Method | Path                                          |
|---------------|--------------------------|--------|-----------------------------------------------|
| scopes.py     | `scopes_list`            | GET    | `/v1.0/scopes`                                |
| events.py     | `events_get_by_id`       | GET    | `/v1.0/event/{event_id}`                      |
| events.py     | `events_query`           | POST   | `/v1.0/event/query`                           |
| events.py     | `events_action`          | POST   | `/v1.0/action/event`                          |
| events.py     | `events_get_task_status` | GET    | `/v1.0/task/{task_id}`                        |
| events.py     | `events_find`            | POST   | `/v1.0/event/query` (server-side pre-filter)  |
| entities.py   | `entities_get_by_id`     | GET    | `/v1.0/search/entity/{entity_id}`             |
| entities.py   | `entities_query`         | POST   | `/v1.0/search/query`                          |
| entities.py   | `entities_find`          | POST   | `/v1.0/search/query` (server-side filtered)   |
| entities.py   | `entities_action`        | POST   | `/v1.0/action/entity`                         |
| exceptions.py | `exceptions_list`        | GET    | `/v1.0/exceptions/{exc_type}`                 |
| exceptions.py | `exceptions_get`         | GET    | `/v1.0/exceptions/{exc_type}/{exc_id}`        |
| exceptions.py | `exceptions_create`      | POST   | `/v1.0/exceptions/{exc_type}`                 |
| exceptions.py | `exceptions_update`      | PUT    | `/v1.0/exceptions/{exc_type}/{exc_id}`        |
| exceptions.py | `exceptions_delete`      | POST   | `/v1.0/exceptions/{exc_type}/delete/{exc_id}` |

`events_find` and `entities_find` are convenience tools that wrap
`POST /v1.0/event/query` and `POST /v1.0/search/query` respectively to locate a specific
message/event (by sender, recipient, subject, message-ID, or entity-ID). They filter
**server-side** — `entities_find` via `entityExtendedFilter`, `events_find` via a
`description` substring pre-filter — default to the last 30 days, and auto-relax
exact→contains (reported as `matchMode`). They do not map to a distinct endpoint.

## URL Reputation, DLP, and Entity Download

| Tool                | HTTP | Path                                                              |
|---------------------|------|-------------------------------------------------------------------|
| `urlrep_list`       | GET  | `/v1.0/sectool-exceptions/avanan_url/exceptions/{exception_type}` |
| `urlrep_get`        | GET  | `/v1.0/sectool-exceptions/avanan_url/exceptions/{exception_type}/{exception_str}` |
| `urlrep_create`     | POST | `/v1.0/sectool-exceptions/avanan_url`                             |
| `urlrep_update`     | PUT  | `/v1.0/sectool-exceptions/avanan_url`                             |
| `urlrep_delete`     | DELETE | `/v1.0/sectool-exceptions/avanan_url/exceptions`                |
| `dlp_list`          | GET  | `/v1.0/sectool-exceptions/avanan_dlp/exceptions/{exception_type}` |
| `dlp_get`           | GET  | `/v1.0/sectool-exceptions/avanan_dlp/exceptions/{exception_type}/{exception_str}` |
| `dlp_create`        | POST | `/v1.0/sectool-exceptions/avanan_dlp`                             |
| `dlp_update`        | PUT  | `/v1.0/sectool-exceptions/avanan_dlp`                             |
| `dlp_delete`        | DELETE | `/v1.0/sectool-exceptions/avanan_dlp/exceptions`                |
| `entities_download` | GET  | `/v1.0/download/entity/{entity_id}?original={true\|false}`         |

Total **26 tools**.
