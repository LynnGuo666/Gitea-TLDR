from __future__ import annotations

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
from tests.conftest import (
    DummyAuthManager,
    DummyDatabase,
    DummyRepoRegistry,
    DummySessionData,
    DummyUserClient,
)


def build_test_client(
    *,
    session: DummySessionData | None = None,
    user_client: DummyUserClient | None = None,
    logged_in: bool = True,
) -> TestClient:
    if session is None and logged_in:
        session = DummySessionData()
    if user_client is None and logged_in:
        user_client = DummyUserClient(
            repos=[{"owner": {"login": "alice"}, "name": "repo-a"}]
        )

    database = DummyDatabase()
    auth_manager = DummyAuthManager(session=session, user_client=user_client)

    context = SimpleNamespace(
        gitea_client=SimpleNamespace(
            list_user_repos=lambda: None,
        ),
        repo_manager=SimpleNamespace(),
        review_engine=SimpleNamespace(
            registry=SimpleNamespace(list_providers=lambda: ["forge"]),
            default_provider_name="forge",
        ),
        webhook_handler=SimpleNamespace(
            parse_review_features=lambda _: ["comment"],
            parse_review_focus=lambda _: ["quality"],
            process_webhook_async=lambda *args, **kwargs: None,
            process_comment_async=lambda *args, **kwargs: None,
            process_issue_async=lambda *args, **kwargs: None,
        ),
        repo_registry=DummyRepoRegistry(),
        auth_manager=auth_manager,
        database=database,
    )

    app = FastAPI()

    @app.middleware("http")
    async def inject_state(request: Request, call_next: Any) -> Any:
        request.state.auth_status = {
            "loggedIn": logged_in,
            "user": session.user if session else None,
        }
        request.state.database = database
        return await call_next(request)

    api_router, public_router, legacy_auth_router = create_api_router(context)
    app.include_router(public_router)
    app.include_router(api_router, prefix="/api")
    app.include_router(legacy_auth_router, prefix="/api")
    return TestClient(app)


def test_old_issue_settings_endpoint_is_removed() -> None:
    client = build_test_client()
    assert client.get("/api/repos/alice/repo-a/issue-settings").status_code == 404


def test_old_my_issues_endpoint_is_removed() -> None:
    client = build_test_client()
    assert client.get("/api/my/issues").status_code == 404


def test_auth_status_when_logged_in() -> None:
    client = build_test_client(session=DummySessionData("alice"))
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["loggedIn"] is True
    assert data["user"]["username"] == "alice"


def test_auth_status_when_logged_out() -> None:
    client = build_test_client(session=None, user_client=None, logged_in=False)
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["loggedIn"] is False
    assert data["user"] is None


def test_auth_login_url_returns_url() -> None:
    client = build_test_client()
    resp = client.get("/api/auth/login-url")
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert data["url"].startswith("https://")
