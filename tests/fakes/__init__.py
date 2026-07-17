"""测试替身集合（阶段 6 新增）。

提供驱动 `WebhookHandler._perform_review` 端到端链路所需的可控替身：

- `FakeGiteaClient`：覆盖 `_perform_review` 调用的全部 Gitea 方法，记录调用
  参数到实例属性供断言，返回合理默认值。
- `FakeRepoManager`：`clone_repository` / `cleanup_repository` no-op，不启真实
  git 子进程；clone 可配置返回路径或抛异常以测试克隆失败分支。
- `StubReviewEngine`：`analyze_pr` 返回可配置 `ReviewResult`（成功 / None /
  raise），复用 `ReviewProvider` 契约。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.review.providers.base import InlineComment, ReviewResult


class FakeGiteaClient:
    """记录式 GiteaClient 替身，覆盖 _perform_review 所需全部方法。

    所有调用参数会追加到对应的 `*_calls` 列表，便于断言调用次数与参数。
    """

    def __init__(
        self,
        *,
        diff_content: str = "diff --git a/file.py b/file.py\n+added line\n",
        pr_data: Optional[Dict[str, Any]] = None,
        clone_url: str = "https://git.example.com/owner/repo.git",
        token: str = "fake-token",
        create_comment_id: int = 1001,
    ) -> None:
        self.token = token
        self._diff = diff_content
        self._pr_data = pr_data or {}
        self._clone_url = clone_url
        self._next_comment_id = create_comment_id

        # 调用记录
        self.create_issue_comment_calls: List[Dict[str, Any]] = []
        self.update_issue_comment_calls: List[Dict[str, Any]] = []
        self.create_commit_status_calls: List[Dict[str, Any]] = []
        self.get_pull_request_diff_calls: List[Dict[str, Any]] = []
        self.get_pull_request_calls: List[Dict[str, Any]] = []
        self.create_review_calls: List[Dict[str, Any]] = []
        self.request_reviewer_calls: List[Dict[str, Any]] = []
        self.get_clone_url_calls: List[Dict[str, Any]] = []

    # ---- _perform_review 直接调用的方法 ----

    async def create_issue_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> Optional[int]:
        self.create_issue_comment_calls.append(
            {"owner": owner, "repo": repo, "pr_number": pr_number, "body": body}
        )
        cid = self._next_comment_id
        self._next_comment_id += 1
        return cid

    async def update_issue_comment(
        self, owner: str, repo: str, comment_id: int, body: str
    ) -> bool:
        self.update_issue_comment_calls.append(
            {"owner": owner, "repo": repo, "comment_id": comment_id, "body": body}
        )
        return True

    async def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        context: str = "pr-reviewer",
        description: str = "",
        target_url: str = "",
    ) -> bool:
        self.create_commit_status_calls.append(
            {
                "owner": owner,
                "repo": repo,
                "sha": sha,
                "state": state,
                "context": context,
                "description": description,
                "target_url": target_url,
            }
        )
        return True

    async def get_pull_request_diff(
        self, owner: str, repo: str, pr_number: int
    ) -> Optional[str]:
        self.get_pull_request_diff_calls.append(
            {"owner": owner, "repo": repo, "pr_number": pr_number}
        )
        return self._diff

    def get_clone_url(self, owner: str, repo: str) -> str:
        self.get_clone_url_calls.append({"owner": owner, "repo": repo})
        return self._clone_url

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: Optional[List[Dict[str, Any]]] = None,
        commit_id: Optional[str] = None,
    ) -> bool:
        self.create_review_calls.append(
            {
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "body": body,
                "event": event,
                "comments": comments,
                "commit_id": commit_id,
            }
        )
        return True

    async def request_reviewer(
        self, owner: str, repo: str, pr_number: int, reviewers: List[str]
    ) -> bool:
        self.request_reviewer_calls.append(
            {
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "reviewers": reviewers,
            }
        )
        return True

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int
    ) -> Optional[Dict[str, Any]]:
        self.get_pull_request_calls.append(
            {"owner": owner, "repo": repo, "pr_number": pr_number}
        )
        return self._pr_data or None

    # ---- 便利断言辅助 ----

    @property
    def commit_status_states(self) -> List[str]:
        return [c["state"] for c in self.create_commit_status_calls]


class FakeRepoManager:
    """no-op RepoManager 替身，不启真实 git 子进程。

    - `clone_repository` 返回配置的 `clone_path`（默认临时目录），记录调用；
      设置 `fail_clone=True` 时抛 RuntimeError 以测试克隆失败分支。
    - `cleanup_repository` no-op，记录调用。
    """

    def __init__(
        self,
        *,
        clone_path: Optional[Path] = None,
        fail_clone: bool = False,
    ) -> None:
        self.clone_path = clone_path or Path("/tmp/fake-repo")
        self.fail_clone = fail_clone
        self.clone_calls: List[Dict[str, Any]] = []
        self.cleanup_calls: List[Dict[str, Any]] = []

    async def clone_repository(
        self,
        clone_url: str,
        owner: str,
        repo: str,
        pr_number: int,
        branch: str,
        auth_token: Optional[str] = None,
    ) -> Optional[Path]:
        self.clone_calls.append(
            {
                "clone_url": clone_url,
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "branch": branch,
                "auth_token": auth_token,
            }
        )
        if self.fail_clone:
            raise RuntimeError("fake clone failure")
        return self.clone_path

    def cleanup_repository(self, owner: str, repo: str, pr_number: int) -> bool:
        self.cleanup_calls.append(
            {"owner": owner, "repo": repo, "pr_number": pr_number}
        )
        return True


class StubReviewEngine:
    """可控 ReviewEngine 替身。

    - `analyze_pr` 返回 `result`（成功）、None（失败，可设 `last_error`）或
      抛 `raise_on_call` 指定的异常（异常分支）。
    - 暴露 `default_provider_name` 与 `last_error` 以对齐 ReviewEngine 契约。
    """

    def __init__(
        self,
        *,
        result: Optional[ReviewResult] = None,
        raise_on_call: Optional[Exception] = None,
        last_error: Optional[str] = None,
        default_provider_name: str = "forge",
    ) -> None:
        self._result = result
        self._raise = raise_on_call
        self.last_error = last_error
        self.default_provider_name = default_provider_name
        self.analyze_pr_calls: List[Dict[str, Any]] = []

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        engine: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: Optional[str] = None,
        wire_api: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        self.analyze_pr_calls.append(
            {
                "repo_path": repo_path,
                "diff_content": diff_content,
                "focus_areas": focus_areas,
                "pr_info": pr_info,
                "api_url": api_url,
                "api_key": api_key,
                "engine": engine,
                "model": model,
                "wire_api": wire_api,
            }
        )
        if self._raise is not None:
            raise self._raise
        if self._result is None:
            # 失败分支：result 为 None 时，last_error 由调用方预设
            return None
        return self._result


def make_review_result(
    *,
    summary: str = "审查完成，未发现严重问题。",
    overview: str = "## 变更概览\n\n本次变更添加了一行代码。",
    inline_comments: Optional[List[InlineComment]] = None,
    overall_severity: Optional[str] = None,
    provider_name: str = "forge",
    usage: Optional[Dict[str, Any]] = None,
) -> ReviewResult:
    """构造一个默认成功的 ReviewResult，便于测试快速组装。"""
    return ReviewResult(
        summary_markdown=summary,
        pr_overview_markdown=overview,
        inline_comments=inline_comments or [],
        overall_severity=overall_severity,
        provider_name=provider_name,
        usage_metadata=usage or {"input_tokens": 100, "output_tokens": 50},
    )
