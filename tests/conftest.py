from __future__ import annotations

import asyncio
import inspect
import os
import sys
import types
from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException, Request, Response


if "nacl" not in sys.modules:
    nacl_module = types.ModuleType("nacl")
    nacl_exceptions = types.ModuleType("nacl.exceptions")
    nacl_public = types.ModuleType("nacl.public")

    class CryptoError(Exception):
        pass

    class PublicKey:
        def __init__(self, data: bytes | None = None):
            self._data = data or b"test-public-key"

        def __bytes__(self):
            return self._data

    class PrivateKey:
        def __init__(self, data: bytes | None = None):
            self._data = data or b"test-private-key"
            self.public_key = PublicKey(self._data)

        @staticmethod
        def generate():
            return PrivateKey(os.urandom(32))

        def __bytes__(self):
            return self._data

    class SealedBox:
        def __init__(self, key):
            self.key = key

        def encrypt(self, payload: bytes) -> bytes:
            key_bytes = bytes(self.key) if hasattr(self.key, "__bytes__") else b"key"
            nonce = os.urandom(8).hex().encode("ascii")
            return key_bytes.hex().encode("ascii") + b":" + nonce + b":" + payload

        def decrypt(self, payload: bytes) -> bytes:
            key_bytes = bytes(self.key) if hasattr(self.key, "__bytes__") else b"key"
            expected = key_bytes.hex().encode("ascii") + b":"
            if not payload.startswith(expected):
                raise CryptoError("wrong key")
            parts = payload.split(b":", 2)
            if len(parts) != 3:
                raise CryptoError("invalid payload")
            return parts[2]

    nacl_exceptions.CryptoError = CryptoError
    nacl_public.PrivateKey = PrivateKey
    nacl_public.PublicKey = PublicKey
    nacl_public.SealedBox = SealedBox

    nacl_module.exceptions = nacl_exceptions
    nacl_module.public = nacl_public

    sys.modules["nacl"] = nacl_module
    sys.modules["nacl.exceptions"] = nacl_exceptions
    sys.modules["nacl.public"] = nacl_public


def pytest_pyfunc_call(pyfuncitem):
    """为仓库内少量 asyncio 测试提供最小运行适配。

    这样在未安装 pytest-asyncio 的环境里，带协程函数的测试也能执行。
    """
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    func_args = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
    }
    asyncio.run(test_func(**func_args))
    return True


# ---------------------------------------------------------------------------
# 共享测试常量（符合 Gitea API 文档格式）
# ---------------------------------------------------------------------------

FAKE_USER_RESPONSE: dict[str, Any] = {
    "id": 1,
    "login": "alice",
    "username": "alice",
    "full_name": "Alice Tester",
    "email": "alice@example.com",
    "avatar_url": "https://git.example.com/avatars/1",
    "is_admin": False,
    "active": True,
}

FAKE_TOKEN_RESPONSE: dict[str, Any] = {
    "access_token": "fake-access-token-value",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_token": "fake-refresh-token",
    "scope": "read:user write:repository",
}

FAKE_REPO: dict[str, Any] = {
    "id": 42,
    "name": "repo-a",
    "full_name": "alice/repo-a",
    "owner": {"id": 1, "login": "alice", "username": "alice"},
    "private": False,
    "description": "",
    "permissions": {"admin": True, "push": True, "pull": True},
}

FAKE_PR: dict[str, Any] = {
    "id": 100,
    "number": 1,
    "title": "Test PR",
    "state": "open",
    "user": {"id": 1, "login": "alice", "username": "alice"},
    "head": {"label": "feat", "ref": "feat", "sha": "abc123"},
    "base": {"label": "main", "ref": "main", "sha": "xyz789"},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "merged": False,
    "draft": False,
    "comments": 0,
    "additions": 10,
    "deletions": 2,
    "changed_files": 1,
}


# ---------------------------------------------------------------------------
# 共享 Dummy 类
# ---------------------------------------------------------------------------


class DummySessionData:
    def __init__(self, username: str = "alice") -> None:
        self.user = {"username": username}


class DummyUserClient:
    def __init__(self, repos: list[dict[str, Any]] | None = None) -> None:
        self._repos = repos

    async def list_user_repos(self) -> list[dict[str, Any]] | None:
        return self._repos


class DummyAuthManager:
    def __init__(
        self,
        session: DummySessionData | None = None,
        user_client: DummyUserClient | None = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self._session = session
        self._user_client = user_client

    def require_session(self, request: Request) -> DummySessionData:
        if self._session is None:
            raise HTTPException(status_code=401, detail="请先登录")
        return self._session

    def get_session(self, request: Request) -> DummySessionData | None:
        return self._session

    async def get_session_async(
        self, request: Request, database: Any = None
    ) -> DummySessionData | None:
        return self._session

    def build_user_client(self, session: DummySessionData) -> DummyUserClient:
        if self._user_client is None:
            raise HTTPException(status_code=502, detail="missing test client")
        return self._user_client

    def get_status_payload(self, request: Request) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "logged_in": self._session is not None,
            "user": self._session.user if self._session else None,
        }

    async def logout_async(
        self, request: Request, response: Response, database: Any = None
    ) -> None:
        response.delete_cookie(key="gitea_session", path="/")

    def build_authorize_url(self) -> str:
        return "https://git.example.com/login/oauth/authorize?client_id=test&state=abc"


class DummyDatabase:
    @asynccontextmanager
    async def session(self):  # type: ignore[override]
        yield object()


class DummyRepoRegistry:
    async def get_secret_async(self, *_: Any) -> None:
        return None

    async def set_secret_async(self, *_: Any) -> None:
        pass

    def set_secret(self, *_: Any) -> None:
        pass

    def delete_secret(self, *_: Any) -> None:
        pass
