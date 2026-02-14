# BACKEND GUIDE

## OVERVIEW
- `app/` is layered as `api -> services -> models`, with `core` for shared infra/config.

## STRUCTURE
```text
app/
├── api/                # HTTP route contracts only
├── core/               # settings, db wiring, app context, auth helpers
├── models/             # SQLAlchemy entities + relationships
└── services/           # orchestration, providers, external clients
```

## WHERE TO PUT CODE
| Change Type | Place | Notes |
|---|---|---|
| New endpoint | `app/api/routes.py` or `app/api/admin_routes.py` | thin handlers; delegate logic |
| New business flow | `app/services/*.py` | orchestration and policy live here |
| New table/entity | `app/models/*.py` | include relationship + export in `models/__init__.py` |
| New env config | `app/core/config.py` | add defaults/docs in `.env.example` and README |
| App startup/middleware | `app/main.py` | context wiring and middlewares only |

## LAYER BOUNDARIES
- API layer
  - parse request and return response.
  - may enforce auth/permission dependencies.
  - avoid embedding multi-step business logic.
- Services layer
  - owns workflow orchestration and external API calls.
  - use `DBService`/`AdminService` or `AsyncSession` consistently.
- Models layer
  - schema, relationship, serialization helpers.
  - no orchestration logic.
- Core layer
  - global settings, db/session factory, app context and shared auth helpers.

## CONVENTIONS
- Use `AsyncSession` and explicit commit semantics for writes.
- Import order: stdlib -> third-party -> local.
- Keep route functions focused; extract repeated permission/validation patterns into services/helpers.
- Service names should communicate domain intent (`webhook_handler`, `admin_service`, `review_engine`).

## ANTI-PATTERNS
- Do not put cross-domain workflow logic in route handlers.
- Do not access DB from frontend-facing code paths outside backend API.
- Do not bypass `admin_required(...)` for admin data mutation endpoints.
- Do not skip token redaction/safe logging in provider/client errors.

## VERIFY FOR BACKEND CHANGES
```bash
ruff check app
mypy app
pytest
```
