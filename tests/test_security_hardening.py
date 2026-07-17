from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import create_api_router
from app.gitea.client import GiteaClient
from app.gitea.repo_manager import RepoManager
from tests.conftest import (
    DummyAuthManager,
    DummyDatabase,
    DummyRepoRegistry,
    DummySessionData,
    DummyUserClient,
)


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
            registry=SimpleNamespace(list_providers=lambda: ["forge"]),
            default_provider_name="forge",
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
    async def test_state_middleware(request: Request, call_next: Any) -> Any:
        request.state.auth_status = auth_status
        request.state.database = database
        return await call_next(request)

    api_router, public_router, legacy_auth_router = create_api_router(context)
    app.include_router(public_router)
    app.include_router(api_router, prefix="/api")
    app.include_router(legacy_auth_router, prefix="/api")

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
def test_old_admin_endpoints_are_removed(path: str) -> None:
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )
    assert client.get(path).status_code == 404


def test_my_reviews_fails_closed_when_gitea_unavailable() -> None:
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=DummyUserClient(repos=None),
        ),
        database=DummyDatabase(),
    )
    assert client.get("/api/my/reviews").status_code == 404


def test_old_my_review_detail_endpoint_is_removed() -> None:
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
    assert client.get("/api/my/reviews/123").status_code == 404


def test_old_my_reviews_endpoint_is_removed() -> None:
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
    assert client.get("/api/my/reviews").status_code == 404


@pytest.mark.asyncio
async def test_clone_repository_never_puts_token_in_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    manager = RepoManager(str(tmp_path))
    captured: dict[str, Any] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProcess:
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        return FakeProcess()

    monkeypatch.setattr(
        "app.gitea.repo_manager.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

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


def test_gitea_client_debug_log_does_not_print_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = GiteaClient("https://gitea.example.com", "tok", debug=True)

    with caplog.at_level("DEBUG"):
        client._log_debug(
            "POST",
            "https://gitea.example.com/api/v1/hooks",
            json={"secret": "abc", "name": "demo"},
        )

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


def test_provider_global_write_requires_admin() -> None:
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )
    assert (
        client.put(
            "/api/config/global?type=review", json={"engine": "claude_code"}
        ).status_code
        == 404
    )


def test_repo_provider_config_write_requires_repo_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NonAdminClient:
        async def check_repo_permissions(
            self, owner: str, repo: str
        ) -> dict[str, bool]:
            return {"admin": False, "push": True, "pull": True}

        async def is_organization(self, owner: str) -> bool:
            return False

    class NonAdminAuthManager(DummyAuthManager):
        def build_user_client(self, session: Any) -> NonAdminClient:
            return NonAdminClient()

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=NonAdminAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=DummyDatabase(),
    )
    assert (
        client.put(
            "/api/repos/owner/repo/config?type=review",
            json={"engine": "claude_code"},
        ).status_code
        == 404
    )


def test_review_settings_write_requires_repo_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NonAdminClient:
        async def check_repo_permissions(
            self, owner: str, repo: str
        ) -> dict[str, bool]:
            return {"admin": False, "push": True, "pull": True}

        async def is_organization(self, owner: str) -> bool:
            return False

    class NonAdminAuthManager(DummyAuthManager):
        def build_user_client(self, session: Any) -> NonAdminClient:
            return NonAdminClient()

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=NonAdminAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=DummyDatabase(),
    )
    assert (
        client.put(
            "/api/repos/owner/repo/review-settings",
            json={"default_focus": ["security"]},
        ).status_code
        == 404
    )


def test_configure_webhook_requires_login() -> None:
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )
    response = client.post(
        "/api/repos/owner/repo/webhook",
        json={"events": ["pull_request"]},
    )
    assert response.status_code == 401


def test_configure_webhook_requires_repo_admin() -> None:
    class NonAdminClient(DummyUserClient):
        async def check_repo_permissions(
            self, owner: str, repo: str
        ) -> dict[str, bool]:
            return {"admin": False, "push": True, "pull": True}

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=NonAdminClient(),
        ),
        database=DummyDatabase(),
    )
    response = client.post(
        "/api/repos/owner/repo/webhook",
        json={"events": ["pull_request"]},
    )
    assert response.status_code == 403


def test_configure_webhook_uses_user_client_and_absolute_default_url() -> None:
    class AdminWebhookClient(DummyUserClient):
        def __init__(self) -> None:
            super().__init__()
            self.hook_definition: dict[str, Any] | None = None

        async def check_repo_permissions(
            self, owner: str, repo: str
        ) -> dict[str, bool]:
            return {"admin": True, "push": True, "pull": True}

        async def ensure_repo_webhook(
            self, owner: str, repo: str, hook_definition: dict[str, Any]
        ) -> int:
            self.hook_definition = hook_definition
            return 123

    user_client = AdminWebhookClient()
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=user_client,
        ),
        database=None,
    )
    response = client.post(
        "/api/repos/owner/repo/webhook",
        json={"events": ["pull_request", "issue_comment"]},
    )
    assert response.status_code == 200
    assert response.json()["hook_id"] == 123
    assert user_client.hook_definition is not None
    assert user_client.hook_definition["events"] == ["pull_request", "issue_comment"]
    assert user_client.hook_definition["config"]["url"] == "http://testserver/webhook"


def test_configure_webhook_rejects_relative_url() -> None:
    class AdminWebhookClient(DummyUserClient):
        async def check_repo_permissions(
            self, owner: str, repo: str
        ) -> dict[str, bool]:
            return {"admin": True, "push": True, "pull": True}

    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=AdminWebhookClient(),
        ),
        database=DummyDatabase(),
    )
    response = client.post(
        "/api/repos/owner/repo/webhook",
        json={"url": "/webhook", "events": ["pull_request"]},
    )
    assert response.status_code == 400


def test_stats_requires_login() -> None:
    client = build_app(
        auth_status={"loggedIn": False, "user": None},
        auth_manager=DummyAuthManager(session=None, user_client=None),
        database=DummyDatabase(),
    )
    assert client.get("/api/stats").status_code == 404


def test_old_repo_provider_config_read_endpoint_is_removed() -> None:
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
    assert client.get("/api/repos/alice/repo-a/config?type=review").status_code == 404


def test_old_inherit_global_write_endpoint_is_removed() -> None:
    client = build_app(
        auth_status={"loggedIn": True, "user": {"username": "alice"}},
        auth_manager=DummyAuthManager(
            session=DummySessionData("alice"),
            user_client=None,
        ),
        database=DummyDatabase(),
    )
    assert (
        client.put(
            "/api/repos/owner/repo/config?type=review",
            json={"inherit_global": True},
        ).status_code
        == 404
    )
