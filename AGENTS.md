# PROJECT KNOWLEDGE BASE

Generated: 2026-02-15 04:32:30 CST  
Commit: `02897f6`  
Branch: `main`

## OVERVIEW
- Stack: FastAPI + SQLAlchemy/Alembic backend, Next.js pages-router frontend (static export), Docker deployment.
- Core domain: Gitea PR review orchestration via multi-provider review engines (`claude_code`, `codex_cli`) + admin/usage dashboards.

## STRUCTURE
```text
.
├── app/                 # Backend (api/core/services/models)
├── frontend/            # Next.js UI (pages/components/lib)
├── alembic/             # DB migrations
├── scripts/             # Operational scripts
├── agents/plan/         # Planned architecture constraints
├── build.sh             # Local image build entry
├── docker-compose.yml   # Runtime orchestration
└── AGENTS.md            # Root contract + hierarchy index
```

## HIERARCHY
- `app/AGENTS.md` - backend layering, placement rules, API/service/model boundaries.
- `app/services/providers/AGENTS.md` - provider engine contracts and safety constraints.
- `frontend/AGENTS.md` - UI layering, route conventions, shared lib/component rules.
- `frontend/pages/AGENTS.md` - page-level patterns (auth, loading/error/empty, dynamic routes).

## WHERE TO LOOK
| Task | Location | Notes |
|---|---|---|
| App bootstrap | `app/main.py` | context creation, middleware, static mount |
| Primary API contract | `app/api/routes.py` | main non-admin endpoints |
| Admin API contract | `app/api/admin_routes.py` | dashboard/admin users/settings/logs |
| DB models | `app/models/` | ORM entities + relationships |
| Business orchestration | `app/services/` | webhook, gitea, db, auth, admin |
| Provider engines | `app/services/providers/` | Claude/Codex implementations |
| Frontend app shell | `frontend/pages/_app.tsx`, `frontend/components/Layout.tsx` | providers, auth refresh, nav |
| Page routes | `frontend/pages/` | pages-router, includes dynamic route |

## GLOBAL RULES
- For Codex/OpenCode: read all files in `agents/plan/` before editing; re-read on updates.
- If guide conflicts with code behavior, follow guide and document the conflict in PR.
- Version sync is mandatory across:
  - `app/core/version.py`
  - `frontend/package.json`
  - `frontend/lib/version.ts`

## CONVENTIONS (PROJECT-SPECIFIC)
- Backend config: define new env fields in `app/core/config.py`, then mirror in `.env.example` and README/docs.
- Frontend API calls must go through backend endpoints only; do not call Gitea/Claude directly from frontend.
- Page title semantics are strict:
  - main page title uses `frontend/components/PageHeader.tsx` (`h1`)
  - section title uses `frontend/components/SectionHeader.tsx` (`h2`)
- Admin entry visibility is role-aware; use auth/admin status endpoints instead of client-side guessing.

## ANTI-PATTERNS
- Do not leak tokens/secrets in logs, URLs, or commit history.
- Do not bypass webhook signature validation when `WEBHOOK_SECRET` is configured.
- Do not use `from x import *` in Python.
- Do not use `any` in frontend; use explicit types / `unknown` + narrowing.
- Do not edit generated/vendor artifacts:
  - `.git/`, `.venv/`, `frontend/node_modules/`, `frontend/.next/`, `frontend/out/`, caches.

## BUILD + VERIFY
```bash
# Backend
uvicorn app.main:app --reload
ruff check app && mypy app && pytest

# Frontend
cd frontend && npm run lint && npx tsc --noEmit && npm run build

# Docker end-to-end
docker compose up --build
```

## RELEASE CHECKLIST
- Update `CHANGELOG.md` for user-visible changes.
- Sync three version files (backend + frontend + frontend lib).
- Rebuild frontend static output after version changes (`cd frontend && npm run build`).
