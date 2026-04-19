from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

from fastapi import FastAPI, HTTPException, Request
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


def test_get_issue_settings_returns_defaults_when_repo_missing(monkeypatch):
    class FakeDBService:
        def __init__(self, session):
            del session

        async def get_repository(self, owner: str, repo_name: str):
            assert owner == "alice"
            assert repo_name == "repo-a"
            return None

    monkeypatch.setattr("app.services.db_service.DBService", FakeDBService)

    client = build_test_client()
    response = client.get("/api/repos/alice/repo-a/issue-settings")

    assert response.status_code == 200
    assert response.json() == {
        "issue_enabled": True,
        "auto_on_open": True,
        "manual_command_enabled": True,
    }


def test_list_my_issues_only_returns_accessible_repositories(monkeypatch):
    class FakeRepo:
        def __init__(self, repo_id: int):
            self.id = repo_id

    class FakeRepositoryRef:
        owner = "alice"
        repo_name = "repo-a"

    class FakeIssue:
        id = 3
        repository_id = 1
        repository = FakeRepositoryRef()
        usage_stats = [
            SimpleNamespace(
                estimated_input_tokens=10,
                estimated_output_tokens=5,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            )
        ]
        issue_number = 77
        issue_title = "Timeout on sync"
        issue_author = "alice"
        issue_state = "open"
        trigger_type = "manual"
        engine = "forge"
        model = "claude-test"
        config_source = "repo_config"
        overall_severity = "medium"
        overall_success = True
        error_message = None
        started_at = None
        completed_at = None
        duration_seconds = 3.2

        @staticmethod
        def get_analysis_payload():
            return {
                "related_issues": [{"number": 11}],
                "solution_suggestions": [{"title": "修复", "summary": "x", "steps": ["a"]}],
            }

    class FakeDBService:
        def __init__(self, session):
            del session

        async def get_repository(self, owner: str, repo_name: str):
            if owner == "alice" and repo_name == "repo-a":
                return FakeRepo(1)
            return None

        async def list_issue_sessions_by_repo_ids(self, repository_ids, success=None, limit=50, offset=0):
            assert repository_ids == [1]
            del success, limit, offset
            return [FakeIssue()]

    monkeypatch.setattr("app.services.db_service.DBService", FakeDBService)

    client = build_test_client()
    response = client.get("/api/my/issues")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["issues"][0]["issue_number"] == 77
    assert data["issues"][0]["related_issue_count"] == 1
    assert data["issues"][0]["solution_count"] == 1
