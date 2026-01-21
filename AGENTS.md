# Repository Guidelines

## Project Structure & Module Organization
- `app/` holds all FastAPI services: `main.py` bootstraps the server, `api/` exposes routes, `services/` houses the Gitea client, webhook handler, repo manager, and Claude integration, while `core/` stores config and version helpers.  
- `frontend/` is a Next.js dashboard; build artifacts land in `frontend/out` and are auto-served when present.  
- Ops artifacts live at the repo root: `.env.example`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, and `build.sh`. Keep new modules aligned with this layout so backends stay under `app/` and UI code under `frontend/`.

## Build, Test, and Development Commands
- Python setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.  
- Run the API: `python app/main.py` (prints version + debug status) or `uvicorn app.main:app --reload`.  
- Frontend: `cd frontend && npm install && npm run build` to produce `out/`.  
- Docker: `docker compose up --build` starts the API, worker, and frontend in one stack. Document any new scripts inside `build.sh`.

## Coding Style & Naming Conventions
- Python code follows PEP 8 with 4-space indentation and full type hints, mirroring existing services.  
- Use descriptive module-level loggers and guard debug logs with `settings.debug`.  
- Environment-driven options belong in `app/core/config.py` with uppercase env names (`AUTO_REQUEST_REVIEWER`, `BOT_USERNAME`, etc.).  
- Frontend components use functional React with hooks and CSS modules already in place; keep file names in `PascalCase.tsx`.

## Testing Guidelines
- There is no automated suite yet; when adding tests place them under `tests/` and use `pytest`. Provide fixtures for webhook payloads and mock Gitea responses via `httpx_mock`.  
- Until tests exist, verify flows manually: trigger `POST /webhook` with sample payloads and confirm PR comments, reviews, statuses, and reviewer assignment occur as expected. Record reproduction steps in PRs.

## Commit & Pull Request Guidelines
- Follow semantic-style commit subjects (`feat:`, `fix:`, `chore:`) consistent with the changelog. Reference modules touched (e.g., `feat: auto-request reviewers in webhook handler`).  
- PRs should include: problem statement, summary of changes, testing evidence (commands or screenshots), configuration updates (env vars, secrets, OAuth values), and **explicit version bumps** when behavior changes ship.
- Update `CHANGELOG.md` when shipping user-visible behavior or configuration changes.
- **Version Synchronization**: When bumping versions, ensure frontend and backend versions stay synchronized:
  - Backend: `app/core/version.py` (`__version__` and `__release_date__`)
  - Frontend: `frontend/package.json` (`version` field)
  - Frontend: `frontend/lib/version.ts` (`FRONTEND_VERSION` and `FRONTEND_RELEASE_DATE`)
  - All three must have the same version number to avoid version mismatch warnings in the UI
  - The version display component in the sidebar will automatically detect and warn about mismatches

## Security & Configuration Tips
- Never commit secrets; rely on `.env` locally and document new variables in `.env.example`.  
- When touching OAuth or webhook features, verify signature validation paths in `app/api/routes.py` and mention any new required headers in the README’s configuration section.  
- Run with `DEBUG=false` before releasing to ensure sensitive payloads are not logged.
