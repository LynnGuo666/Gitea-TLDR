from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import create_api_router


class DummySessionData:
    def __init__(self, username: str = "alice"):
        self.user = {"username": username}


class DummyUserClient:
    def __init__(self, repos: list[dict[str, Any]] | None):
        self._repos = repos

    async def list_user_repos(self):
        return self._repos


class DummyAuthManager:
    def __init__(self):
        self.enabled = True

    def require_session(self, request: Request):
        del request
        return DummySessionData()

    def build_user_client(self, session: DummySessionData):
        del session
        return DummyUserClient(repos=[{"owner": {"login": "alice"}, "name": "repo-a"}])

    def get_status_payload(self, request: Request):
        del request
        return {"enabled": True, "logged_in": True, "user": {"username": "alice"}}


class DummyRepoRegistry:
    async def get_secret_async(self, *_):
        return None


class DummyDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def build_test_client() -> TestClient:
    database = DummyDatabase()
    context = SimpleNamespace(
        gitea_client=SimpleNamespace(),
        repo_manager=SimpleNamespace(),
        review_engine=SimpleNamespace(
            registry=SimpleNamespace(list_providers=lambda: ["claude_code", "forge"]),
            default_provider_name="claude_code",
        ),
        webhook_handler=SimpleNamespace(
            parse_review_features=lambda _: ["comment"],
            parse_review_focus=lambda _: ["quality"],
            process_webhook_async=lambda *args, **kwargs: None,
            process_comment_async=lambda *args, **kwargs: None,
            process_issue_async=lambda *args, **kwargs: None,
        ),
        repo_registry=DummyRepoRegistry(),
        auth_manager=DummyAuthManager(),
        database=database,
    )

    app = FastAPI()

    @app.middleware("http")
    async def inject_state(request: Request, call_next):
        request.state.auth_status = {"loggedIn": True, "user": {"username": "alice"}}
        request.state.database = database
        return await call_next(request)

    api_router, public_router = create_api_router(context)
    app.include_router(public_router)
    app.include_router(api_router, prefix="/api")
    return TestClient(app)


def test_old_issue_settings_endpoint_is_removed():
    client = build_test_client()
    response = client.get("/api/repos/alice/repo-a/issue-settings")

    assert response.status_code == 404


def test_old_my_issues_endpoint_is_removed():
    client = build_test_client()
    response = client.get("/api/my/issues")

    assert response.status_code == 404
