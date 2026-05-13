"""AuthManager 单元测试，HTTP 调用全部 monkeypatch。"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

import pytest
from fastapi import HTTPException, Response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.conftest import FAKE_TOKEN_RESPONSE, FAKE_USER_RESPONSE


def _make_settings(**overrides: Any) -> SimpleNamespace:
    base = dict(
        gitea_url="https://git.example.com",
        oauth_client_id="test-client-id",
        oauth_client_secret="test-secret",
        oauth_redirect_url="http://localhost:8000/api/auth/callback",
        oauth_scopes=["read:user", "write:repository"],
        session_cookie_name="gitea_session",
        session_cookie_secure=False,
        debug=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_auth_manager(monkeypatch: pytest.MonkeyPatch, **settings_overrides: Any):
    from app.gitea import auth as am_module

    fake_settings = _make_settings(**settings_overrides)
    monkeypatch.setattr(am_module, "settings", fake_settings)
    from app.gitea.auth import AuthManager

    return AuthManager()


def test_disabled_when_no_oauth_config(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = _make_auth_manager(
        monkeypatch, oauth_client_id=None, oauth_redirect_url=None
    )
    assert not mgr.enabled


def test_enabled_when_oauth_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = _make_auth_manager(monkeypatch)
    assert mgr.enabled


def test_build_authorize_url_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    from urllib.parse import parse_qs, urlparse

    mgr = _make_auth_manager(monkeypatch)
    url = mgr.build_authorize_url()
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert params["response_type"] == ["code"]
    assert params["client_id"] == ["test-client-id"]
    assert params["redirect_uri"] == ["http://localhost:8000/api/auth/callback"]
    assert "state" in params


def test_build_authorize_url_raises_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = _make_auth_manager(
        monkeypatch, oauth_client_id=None, oauth_redirect_url=None
    )
    with pytest.raises(HTTPException) as exc_info:
        mgr.build_authorize_url()
    assert exc_info.value.status_code == 400


def test_state_expired_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = _make_auth_manager(monkeypatch)
    state = mgr._generate_state()
    # 强制过期：将过期时间设为过去
    mgr._state_store[state] = time.time() - 1
    assert not mgr._consume_state(state)


def test_state_can_only_be_consumed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = _make_auth_manager(monkeypatch)
    state = mgr._generate_state()
    assert mgr._consume_state(state)
    assert not mgr._consume_state(state)


async def test_handle_callback_rejects_bad_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = _make_auth_manager(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        await mgr.handle_callback("some-code", "wrong-state", Response())
    assert exc_info.value.status_code == 400


async def test_handle_callback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = _make_auth_manager(monkeypatch)

    async def fake_exchange(code: str) -> dict[str, Any]:
        return FAKE_TOKEN_RESPONSE

    async def fake_fetch_user(token: str) -> dict[str, Any]:
        return FAKE_USER_RESPONSE

    monkeypatch.setattr(mgr, "_exchange_code", fake_exchange)
    monkeypatch.setattr(mgr, "_fetch_user", fake_fetch_user)

    state = mgr._generate_state()
    response = Response()
    await mgr.handle_callback("auth-code", state, response, database=None)

    assert mgr._sessions
    session = list(mgr._sessions.values())[0]
    assert session.access_token == "fake-access-token-value"
    assert session.user["username"] == "alice"
    assert session.user["full_name"] == "Alice Tester"
    assert session.user["avatar_url"] == "https://git.example.com/avatars/1"

    # cookie 已设置
    set_cookie = response.headers.get("set-cookie", "")
    assert "gitea_session" in set_cookie


async def test_handle_callback_raises_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = _make_auth_manager(
        monkeypatch, oauth_client_id=None, oauth_redirect_url=None
    )
    with pytest.raises(HTTPException) as exc_info:
        await mgr.handle_callback("code", "state", Response())
    assert exc_info.value.status_code == 400


def test_get_session_expired_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.gitea.auth import SessionData

    mgr = _make_auth_manager(monkeypatch)
    session_id = "test-session-id"
    mgr._sessions[session_id] = SessionData(
        access_token="tok",
        refresh_token=None,
        scope="",
        expires_at=time.time() - 1,  # 已过期
        user={"username": "alice"},
    )

    from starlette.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    client = TestClient(app, cookies={"gitea_session": session_id})

    # 通过 Request 对象调用 get_session
    from starlette.requests import Request as StarletteRequest
    from starlette.datastructures import Headers

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", f"gitea_session={session_id}".encode())],
        "query_string": b"",
    }
    request = StarletteRequest(scope)
    result = mgr.get_session(request)
    assert result is None
    assert session_id not in mgr._sessions


def test_logout_clears_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.gitea.auth import SessionData
    from starlette.requests import Request as StarletteRequest

    mgr = _make_auth_manager(monkeypatch)
    session_id = "logout-session-id"
    mgr._sessions[session_id] = SessionData(
        access_token="tok",
        refresh_token=None,
        scope="",
        expires_at=time.time() + 3600,
        user={"username": "alice"},
    )

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"cookie", f"gitea_session={session_id}".encode())],
        "query_string": b"",
    }
    request = StarletteRequest(scope)
    response = Response()
    mgr.logout(request, response)

    assert session_id not in mgr._sessions
    set_cookie = response.headers.get("set-cookie", "")
    assert "gitea_session" in set_cookie
