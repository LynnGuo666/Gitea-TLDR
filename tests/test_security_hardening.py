from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import create_api_router
from app.services.gitea_client import GiteaClient
from app.services.repo_manager import RepoManager


class DummyUserClient:
    def __init__(self, repos: list[dict[str, Any]] | None):
        self._repos = repos

    async def list_user_repos(self):
        return self._repos


class DummySessionData:
    def __init__(self, username: str = "alice"):
        self.user = {"username": username}


class DummyAuthManager:
    def __init__(self, session: DummySessionData | None, user_client: DummyUserClient | None):
        self._session = session
        self._user_client = user_client
        self.enabled = True

    def require_session(self, request: Request):
        if self._session is None:
            raise HTTPException(status_code=401, detail="请先登录")
        return self._session

    def build_user_client(self, session: DummySessionData):
        if self._user_client is None:
            raise HTTPException(status_code=502, detail="missing test client")
        return self._user_client

    def get_session(self, request: Request):
        return self._session

    def get_status_payload(self, request: Request):
        return {"enabled": True, "logged_in": self._session is not None, "user": self._session.user if self._session else None}


class DummyDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


class DummyRepoRegistry:
    async def get_secret_async(self, *_):
        return None

    async def set_secret_async(self, *_):
        pass

    def set_secret(self, *_):
        pass

    def delete_secret(self, *_):
        pass


def build_app(
    *,
    auth_status: dict[str, Any],
    auth_manager: DummyAuthManager,
    database: Any,
) -> TestClient:
    context = SimpleNamespace(
        gitea_client=SimpleNamespace(),
        repo_manager=SimpleNamespace(),
        review_engine=SimpleNamespace(
            registry=SimpleNamespace(list_providers=lambda: ["claude_code"]),
            default_provider_name="claude_code",
        ),
        webhook_handler=SimpleNamespace(
            parse_review_features=lambda _: ["comment"],
            parse_review_focus=lambda _: ["quality"],
            process_webhook_async=lambda *args, **kwargs: None,
            process_comment_async=lambda *args, **kwargs: None,
        ),
        repo_registry=DummyRepoRegistry(),
        auth_manager=auth_manager,
        database=database,
    )

    app = FastAPI()

    @app.middleware("http")
    async def test_state_middleware(request: Request, call_next):
        request.state.auth_status = auth_status
        request.state.database = database
        return await call_next(request)

    api_router, public_router = create_api_router(context)
    app.include_router(public_router)
    app.include_router(api_router, prefix="/api")

    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/api/reviews",
        "/api/reviews/1",
        "/api/configs",
        "/api/repositories",
    ],
)
def test_old_admin_endpoints_are_removed(path: str):
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )

    resp = client.get(path)
    assert resp.status_code == 404


def test_my_reviews_fails_closed_when_gitea_unavailable():
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=DummyUserClient(repos=None),
        ),
        database=DummyDatabase(),
    )

    resp = client.get("/api/my/reviews")
    assert resp.status_code == 404


def test_old_my_review_detail_endpoint_is_removed():
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=DummyUserClient(
                repos=[{"owner": {"login": "alice"}, "name": "repo-a"}]
            ),
        ),
        database=DummyDatabase(),
    )

    resp = client.get("/api/my/reviews/123")
    assert resp.status_code == 404


def test_old_my_reviews_endpoint_is_removed():
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=DummyUserClient(
                repos=[
                    {"owner": {"login": "alice"}, "name": "repo-a"},
                    {"owner": {"login": "bob"}, "name": "repo-b"},
                ]
            ),
        ),
        database=DummyDatabase(),
    )

    resp = client.get("/api/my/reviews")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_clone_repository_never_puts_token_in_command(monkeypatch: pytest.MonkeyPatch, tmp_path):
    manager = RepoManager(str(tmp_path))
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        return FakeProcess()

    monkeypatch.setattr("app.services.repo_manager.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    token = "secret-token-value"
    result = await manager.clone_repository(
        "https://gitea.example.com/team/repo.git",
        "team",
        "repo",
        100,
        "main",
        auth_token=token,
    )

    assert result is not None
    joined_args = " ".join(str(x) for x in captured["args"])
    assert token not in joined_args
    assert captured["env"].get("GIT_ASKPASS")
    assert captured["env"].get("GITEA_TOKEN") == token


def test_gitea_client_debug_log_does_not_print_secret(caplog: pytest.LogCaptureFixture):
    client = GiteaClient("https://gitea.example.com", "tok", debug=True)

    with caplog.at_level("DEBUG"):
        client._log_debug("POST", "https://gitea.example.com/api/v1/hooks", json={"secret": "abc", "name": "demo"})

    assert "abc" not in caplog.text
    assert "请求体字段" in caplog.text

    redacted = client._redact_mapping(
        {
            "Authorization": "token x",
            "config": {"secret": "abc", "url": "https://x"},
            "normal": "ok",
        }
    )
    assert redacted["Authorization"] == "***"
    assert redacted["config"]["secret"] == "***"
    assert redacted["normal"] == "ok"


# ==================== 新增安全测试 ====================

def test_provider_global_write_requires_admin():
    """旧全局配置写入端点已删除。"""
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )

    resp = client.put("/api/config/global?type=review", json={"engine": "claude_code"})
    assert resp.status_code == 404


def test_repo_provider_config_write_requires_repo_admin(monkeypatch: pytest.MonkeyPatch):
    """旧仓库配置写入端点已删除。"""

    class NonAdminClient:
        async def check_repo_permissions(self, owner, repo):
            return {"admin": False, "push": True, "pull": True}

        async def is_organization(self, owner):
            return False

    class NonAdminAuthManager(DummyAuthManager):
        def build_user_client(self, session):
            return NonAdminClient()

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=NonAdminAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=DummyDatabase(),
    )

    resp = client.put(
        "/api/repos/owner/repo/config?type=review",
        json={"engine": "claude_code"},
    )
    assert resp.status_code == 404


def test_review_settings_write_requires_repo_admin(monkeypatch: pytest.MonkeyPatch):
    """旧 review-settings 写入端点已删除。"""

    class NonAdminClient:
        async def check_repo_permissions(self, owner, repo):
            return {"admin": False, "push": True, "pull": True}

        async def is_organization(self, owner):
            return False

    class NonAdminAuthManager(DummyAuthManager):
        def build_user_client(self, session):
            return NonAdminClient()

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=NonAdminAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=DummyDatabase(),
    )

    resp = client.put(
        "/api/repos/owner/repo/review-settings",
        json={"default_focus": ["security"]},
    )
    assert resp.status_code == 404


def test_stats_requires_login():
    """旧 stats 端点已删除。"""
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )

    resp = client.get("/api/stats")
    assert resp.status_code == 404


def test_old_repo_provider_config_read_endpoint_is_removed():
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=DummyUserClient(
                repos=[{"owner": {"login": "alice"}, "name": "repo-a"}]
            ),
        ),
        database=DummyDatabase(),
    )

    resp = client.get("/api/repos/alice/repo-a/config?type=review")
    assert resp.status_code == 404


def test_old_inherit_global_write_endpoint_is_removed():
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=DummyDatabase(),
    )

    resp = client.put(
        "/api/repos/owner/repo/config?type=review",
        json={"inherit_global": True},
    )
    assert resp.status_code == 404
