"""GiteaClient 单元测试，全部 mock httpx。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.gitea_client import GiteaClient
from tests.conftest import FAKE_PR, FAKE_REPO


def _make_client() -> GiteaClient:
    return GiteaClient("https://git.example.com", "test-token")


class _MockResponse:
    def __init__(self, data: Any, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx
            from unittest.mock import MagicMock

            mock_response = MagicMock()
            mock_response.status_code = self.status_code
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=mock_response,
            )


class _MockAsyncClient:
    def __init__(self, responses: list[_MockResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def __aenter__(self) -> "_MockAsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    def _next(self) -> _MockResponse:
        resp = self._responses[self._index]
        self._index = min(self._index + 1, len(self._responses) - 1)
        return resp

    async def get(self, *_: Any, **__: Any) -> _MockResponse:
        return self._next()

    async def post(self, *_: Any, **__: Any) -> _MockResponse:
        return self._next()

    async def patch(self, *_: Any, **__: Any) -> _MockResponse:
        return self._next()


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, *responses: _MockResponse) -> None:
    mock = _MockAsyncClient(list(responses))
    monkeypatch.setattr(
        "app.services.gitea_client.httpx.AsyncClient",
        lambda **_: mock,
    )


# ---------------------------------------------------------------------------
# list_pull_requests
# ---------------------------------------------------------------------------


async def test_list_pull_requests_returns_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse([FAKE_PR]))
    client = _make_client()
    prs = await client.list_pull_requests("alice", "repo-a")
    assert isinstance(prs, list)
    assert prs[0]["number"] == 1
    assert prs[0]["state"] == "open"
    assert prs[0]["head"]["ref"] == "feat"
    assert prs[0]["base"]["ref"] == "main"
    assert prs[0]["user"]["login"] == "alice"


async def test_list_pull_requests_returns_none_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=500))
    client = _make_client()
    result = await client.list_pull_requests("alice", "repo-a")
    assert result is None


# ---------------------------------------------------------------------------
# list_user_repos
# ---------------------------------------------------------------------------


async def test_list_user_repos_returns_repo_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse([FAKE_REPO]), _MockResponse([]))
    client = _make_client()
    repos = await client.list_user_repos()
    assert repos is not None
    assert repos[0]["full_name"] == "alice/repo-a"
    assert repos[0]["name"] == "repo-a"
    assert repos[0]["owner"]["login"] == "alice"
    assert "permissions" in repos[0]
    assert "admin" in repos[0]["permissions"]


async def test_list_user_repos_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    page1 = [dict(FAKE_REPO, id=i, name=f"repo-{i}") for i in range(50)]
    _patch_httpx(monkeypatch, _MockResponse(page1), _MockResponse([]))
    client = _make_client()
    repos = await client.list_user_repos()
    assert repos is not None
    assert len(repos) == 50


async def test_list_user_repos_returns_none_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=401))
    client = _make_client()
    result = await client.list_user_repos()
    assert result is None


# ---------------------------------------------------------------------------
# check_repo_permissions / get_repository
# ---------------------------------------------------------------------------


async def test_get_repository_returns_permissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse(FAKE_REPO))
    client = _make_client()
    perms = await client.check_repo_permissions("alice", "repo-a")
    assert perms is not None
    assert perms["admin"] is True
    assert perms["push"] is True
    assert perms["pull"] is True


async def test_check_repo_permissions_returns_none_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=404))
    client = _make_client()
    result = await client.check_repo_permissions("alice", "missing-repo")
    assert result is None


# ---------------------------------------------------------------------------
# create_repo_hook
# ---------------------------------------------------------------------------


async def test_create_repo_hook_returns_id(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_hook_response = {"id": 99, "type": "gitea", "active": True}
    _patch_httpx(monkeypatch, _MockResponse(mock_hook_response, status_code=201))
    client = _make_client()
    hook_def = {
        "type": "gitea",
        "active": True,
        "events": ["pull_request", "issues", "issue_comment"],
        "config": {"url": "https://app/webhook", "content_type": "json"},
    }
    hook_id = await client.create_repo_hook("alice", "repo-a", hook_def)
    assert hook_id == 99


# ---------------------------------------------------------------------------
# ensure_repo_webhook
# ---------------------------------------------------------------------------


async def test_ensure_repo_webhook_updates_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_hook = {
        "id": 55,
        "type": "gitea",
        "active": True,
        "config": {"url": "https://app/webhook", "content_type": "json"},
    }
    # list_repo_hooks → existing hook; update_repo_hook → 200
    _patch_httpx(
        monkeypatch,
        _MockResponse([existing_hook]),
        _MockResponse({}, status_code=200),
    )
    client = _make_client()
    hook_def = {
        "type": "gitea",
        "active": True,
        "events": ["pull_request"],
        "config": {"url": "https://app/webhook", "content_type": "json"},
    }
    hook_id = await client.ensure_repo_webhook("alice", "repo-a", hook_def)
    assert hook_id == 55


# ---------------------------------------------------------------------------
# _redact_mapping
# ---------------------------------------------------------------------------


def test_redact_mapping_hides_secret() -> None:
    client = _make_client()
    result = client._redact_mapping(
        {
            "Authorization": "token abc",
            "config": {"secret": "xyz", "url": "https://ok"},
            "name": "ok",
        }
    )
    assert result["Authorization"] == "***"
    assert result["config"]["secret"] == "***"
    assert result["config"]["url"] == "https://ok"
    assert result["name"] == "ok"


def test_redact_mapping_handles_nested_list() -> None:
    client = _make_client()
    result = client._redact_mapping(
        {"items": [{"token": "secret", "label": "visible"}]}
    )
    assert result["items"][0]["token"] == "***"
    assert result["items"][0]["label"] == "visible"


# ---------------------------------------------------------------------------
# create_issue_comment
# ---------------------------------------------------------------------------


async def test_create_issue_comment_returns_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({"id": 42}, status_code=201))
    client = _make_client()
    comment_id = await client.create_issue_comment("alice", "repo-a", 1, "LGTM")
    assert comment_id == 42


async def test_create_issue_comment_returns_none_on_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=403))
    client = _make_client()
    result = await client.create_issue_comment("alice", "repo-a", 1, "body")
    assert result is None


# ---------------------------------------------------------------------------
# create_review
# ---------------------------------------------------------------------------


async def test_create_review_returns_true_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=200))
    client = _make_client()
    ok = await client.create_review("alice", "repo-a", 1, "Looks good", event="COMMENT")
    assert ok is True


async def test_create_review_returns_false_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=403))
    client = _make_client()
    ok = await client.create_review("alice", "repo-a", 1, "body")
    assert ok is False


# ---------------------------------------------------------------------------
# is_organization
# ---------------------------------------------------------------------------


async def test_is_organization_returns_false_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({}, status_code=404))
    client = _make_client()
    result = await client.is_organization("alice")
    assert result is False


async def test_is_organization_returns_true_on_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_httpx(monkeypatch, _MockResponse({"name": "myorg"}, status_code=200))
    client = _make_client()
    result = await client.is_organization("myorg")
    assert result is True
