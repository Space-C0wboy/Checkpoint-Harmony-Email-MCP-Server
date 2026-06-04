# Harmony Email & Collaboration — Endpoint Inventory

Derived from `spec.json` (OpenAPI 3.0.2, smart-api v1.50). All paths are relative
to `CHECKPOINT_API_URL` (region gateway + `/app/hec-api`). `POST /auth/external`
is handled internally by the TokenManager and is not a tool.

| Module        | Tool                     | Method | Path                                          |
|---------------|--------------------------|--------|-----------------------------------------------|
| scopes.py     | `scopes_list`            | GET    | `/v1.0/scopes`                                |
| events.py     | `events_get_by_id`       | GET    | `/v1.0/event/{event_id}`                      |
| events.py     | `events_query`           | POST   | `/v1.0/event/query`                           |
| events.py     | `events_action`          | POST   | `/v1.0/action/event`                          |
| events.py     | `events_get_task_status` | GET    | `/v1.0/task/{task_id}`                        |
| entities.py   | `entities_get_by_id`     | GET    | `/v1.0/search/entity/{entity_id}`             |
| entities.py   | `entities_query`         | POST   | `/v1.0/search/query`                          |
| entities.py   | `entities_action`        | POST   | `/v1.0/action/entity`                         |
| exceptions.py | `exceptions_list`        | GET    | `/v1.0/exceptions/{exc_type}`                 |
| exceptions.py | `exceptions_get`         | GET    | `/v1.0/exceptions/{exc_type}/{exc_id}`        |
| exceptions.py | `exceptions_create`      | POST   | `/v1.0/exceptions/{exc_type}`                 |
| exceptions.py | `exceptions_update`      | PUT    | `/v1.0/exceptions/{exc_type}/{exc_id}`        |
| exceptions.py | `exceptions_delete`      | POST   | `/v1.0/exceptions/{exc_type}/delete/{exc_id}` |
