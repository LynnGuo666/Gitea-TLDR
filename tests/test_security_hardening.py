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
def test_admin_endpoints_require_auth(path: str):
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )

    resp = client.get(path)
    assert resp.status_code == 401


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
    assert resp.status_code == 502
    assert "Gitea" in resp.json().get("detail", "")


def test_my_review_detail_returns_404_for_inaccessible_repo(monkeypatch: pytest.MonkeyPatch):
    class FakeRepo:
        def __init__(self, repo_id: int):
            self.id = repo_id

    class FakeReview:
        def __init__(self, repository_id: int):
            self.repository_id = repository_id

    class FakeDBService:
        def __init__(self, session):
            self.session = session

        async def get_repository(self, owner: str, repo_name: str):
            if owner == "alice" and repo_name == "repo-a":
                return FakeRepo(1)
            return None

        async def get_review_session(self, review_id: int):
            return FakeReview(2)

        async def get_inline_comments(self, review_id: int):
            return []

    monkeypatch.setattr("app.services.db_service.DBService", FakeDBService)

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


def test_my_reviews_only_returns_accessible_repositories(monkeypatch: pytest.MonkeyPatch):
    class FakeRepo:
        def __init__(self, repo_id: int):
            self.id = repo_id

    class FakeRepositoryRef:
        owner = "alice"
        repo_name = "repo-a"

    class FakeReview:
        id = 7
        repository_id = 1
        repository = FakeRepositoryRef()
        usage_stat = SimpleNamespace(
            estimated_input_tokens=120,
            estimated_output_tokens=30,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=5,
        )
        pr_number = 10
        pr_title = "Fix bug"
        pr_author = "alice"
        trigger_type = "manual"
        engine = "claude_code"
        analysis_mode = "simple"
        model = "model-x"
        config_source = "repo_config"
        overall_severity = "low"
        overall_success = True
        error_message = None
        inline_comments_count = 0
        started_at = None
        completed_at = None
        duration_seconds = 1.0

        @staticmethod
        def get_features():
            return ["comment"]

        @staticmethod
        def get_focus():
            return ["quality"]

    class FakeDBService:
        def __init__(self, session):
            self.session = session

        async def get_repository(self, owner: str, repo_name: str):
            if owner == "alice" and repo_name == "repo-a":
                return FakeRepo(1)
            return None

        async def list_review_sessions_by_repo_ids(
            self,
            repository_ids,
            success=None,
            limit=50,
            offset=0,
        ):
            assert repository_ids == [1]
            return [FakeReview()]

    monkeypatch.setattr("app.services.db_service.DBService", FakeDBService)

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
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["reviews"][0]["repo_full_name"] == "alice/repo-a"
    assert body["reviews"][0]["estimated_input_tokens"] == 120
    assert body["reviews"][0]["estimated_output_tokens"] == 30
    assert body["reviews"][0]["total_tokens"] == 150


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
    """非 admin 用户 PUT /api/config/global?type=review 应返回 401（未配置 admin 时依赖链抛 401）"""
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )

    resp = client.put("/api/config/global?type=review", json={"engine": "claude_code"})
    # admin_required 在无 admin DB 时会抛 401/403
    assert resp.status_code in (401, 403)


def test_repo_provider_config_write_requires_repo_admin(monkeypatch: pytest.MonkeyPatch):
    """无仓库 admin 权限的已登录用户 PUT /api/repos/.../config?type=review 应返回 403"""

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
    assert resp.status_code == 403


def test_review_settings_write_requires_repo_admin(monkeypatch: pytest.MonkeyPatch):
    """无仓库 admin 权限的已登录用户 PUT /api/repos/.../review-settings 应返回 403"""

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
    assert resp.status_code == 403


def test_stats_requires_login():
    """未登录用户 GET /api/stats 应返回 401"""
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )

    resp = client.get("/api/stats")
    assert resp.status_code == 401


def test_repo_provider_config_uses_global_model_when_repo_only_has_review_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRepo:
        id = 1

    class FakeConfig:
        def __init__(
            self,
            *,
            repository_id,
            engine,
            model=None,
            api_url=None,
            api_key=None,
            wire_api=None,
            default_focus=None,
            default_features=None,
        ):
            self.repository_id = repository_id
            self.engine = engine
            self.model = model
            self.api_url = api_url
            self.api_key = api_key
            self.wire_api = wire_api
            self.default_focus = default_focus
            self.default_features = default_features
            self.max_tokens = None
            self.temperature = None
            self.custom_prompt = None

    repo_config = FakeConfig(
        repository_id=1,
        engine="claude_code",
        default_focus='["security"]',
    )
    global_config = FakeConfig(
        repository_id=None,
        engine="forge",
        model="claude-sonnet-4-20250514",
        api_url="https://api.example.com",
    )

    class FakeDBService:
        def __init__(self, session):
            self.session = session

        async def get_repository(self, owner: str, repo_name: str):
            return FakeRepo()

        async def get_global_model_config(self):
            return global_config

        async def get_repo_specific_model_config(self, repository_id: int):
            assert repository_id == 1
            return repo_config

    monkeypatch.setattr("app.services.db_service.DBService", FakeDBService)

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
    assert resp.status_code == 200
    body = resp.json()
    assert body["inherit_global"] is True
    assert body["engine"] == "forge"
    assert body["model"] == "claude-sonnet-4-20250514"


def test_inherit_global_preserves_repo_review_settings_instead_of_deleting_config(
    monkeypatch: pytest.MonkeyPatch,
):
    class AdminClient:
        async def check_repo_permissions(self, owner, repo):
            return {"admin": True, "push": True, "pull": True}

        async def is_organization(self, owner):
            return False

    class AdminAuthManager(DummyAuthManager):
        def build_user_client(self, session):
            return AdminClient()

    class FakeSession:
        async def flush(self):
            return None

    class FakeDatabase:
        @asynccontextmanager
        async def session(self):
            yield FakeSession()

    class FakeRepo:
        id = 1

    class FakeConfig:
        def __init__(self):
            self.repository_id = 1
            self.engine = "forge"
            self.model = "repo-model"
            self.api_url = "https://repo.example.com"
            self.api_key = None
            self.wire_api = "responses"
            self.default_focus = '["security"]'
            self.default_features = '["comment"]'
            self.max_tokens = None
            self.temperature = None
            self.custom_prompt = None

    repo_config = FakeConfig()
    deleted: list[int] = []

    class FakeDBService:
        def __init__(self, session):
            self.session = session

        async def get_repository(self, owner: str, repo_name: str):
            return FakeRepo()

        async def get_repo_specific_model_config(self, repository_id: int):
            return repo_config

        async def delete_repo_model_config(self, repository_id: int):
            deleted.append(repository_id)
            return True

        async def get_global_model_config(self):
            return None

    monkeypatch.setattr("app.services.db_service.DBService", FakeDBService)

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=AdminAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=FakeDatabase(),
    )

    resp = client.put(
        "/api/repos/owner/repo/config?type=review",
        json={"inherit_global": True},
    )
    assert resp.status_code == 200
    assert deleted == []
    assert repo_config.default_focus == '["security"]'
    assert repo_config.model is None
    assert repo_config.api_url is None
