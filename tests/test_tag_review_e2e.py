"""验证 tag 区间审查编排的端到端 mock 测试。

复用 conftest 的 nacl stub 与 pytest 异步适配。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.review.providers.base import ReviewResult
from app.review.webhook_handler import WebhookHandler


class FakeRepoManager:
    def __init__(self) -> None:
        self.cleaned = False

    async def clone_for_compare(self, *args: Any, **kwargs: Any) -> Path:
        return Path("/tmp/fake-repo")

    def cleanup_compare_workspace(self, *args: Any, **kwargs: Any) -> bool:
        self.cleaned = True
        return True


class FakeEngine:
    default_provider_name = "forge"
    last_error: str | None = None

    async def analyze_pr(self, *args: Any, **kwargs: Any) -> ReviewResult:
        return ReviewResult(
            summary_markdown="## tag 区间审查摘要\n本次变更未发现风险点。",
            overall_severity="none",
            provider_name="forge",
            usage_metadata={"input_tokens": 100, "output_tokens": 50, "model": "test"},
        )


class FakeGiteaClient:
    base_url = "https://git.example.com"
    token = "fake-token"

    def __init__(self) -> None:
        self.statuses: list[tuple[str, str, str]] = []

    async def get_tag_sha(self, owner: str, repo: str, tag: str) -> str:
        return f"sha-{tag}"

    async def compare_tags(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        return {
            "commits": [],
            "files": [{"filename": "a.py", "patch": "@@ -1 +1 @@\n-old\n+new\n"}],
        }

    async def list_tags(self, owner: str, repo: str, limit: int = 50) -> list[dict[str, Any]]:
        return [{"name": "v1.1.0"}, {"name": "v1.0.0"}]

    async def create_commit_status(
        self, owner: str, repo: str, sha: str, state: str, description: str = "", **kw: Any
    ) -> bool:
        self.statuses.append((sha, state, description))
        return True

    def get_clone_url(self, owner: str, repo: str) -> str:
        return f"{self.base_url}/{owner}/{repo}.git"


async def _run_tag_review_e2e() -> None:
    from sqlalchemy import text

    from app.core.database import Database

    db = Database("sqlite+aiosqlite:///:memory:")
    await db.init()
    await db.create_tables()

    # 注入最小 review 配置 + 凭证，让 perform_tag_review 能走过配置检查
    async with db.session() as session:
        await session.execute(text("INSERT INTO repositories (provider, owner, name, full_name, is_active, created_at, updated_at) VALUES ('gitea','alice','repo-a','alice/repo-a',1,datetime('now'),datetime('now'))"))
        await session.execute(text("INSERT INTO provider_credentials (scope_type, scope_key, name, provider, api_url, api_key_enc, is_active, created_at, updated_at) VALUES ('system','system','test','anthropic','https://api.anthropic.com','enc',1,datetime('now'),datetime('now'))"))
        await session.execute(text("INSERT INTO repository_configs (repository_id, scenario, engine, credential_id, is_active, features_json, focus_json, created_at, updated_at) VALUES (1,'review','forge',1,1,'[\"status\"]','[\"quality\"]',datetime('now'),datetime('now'))"))

    gitea = FakeGiteaClient()
    handler = WebhookHandler(
        gitea_client=gitea,
        repo_manager=FakeRepoManager(),
        review_engine=FakeEngine(),
        database=db,
        bot_username=None,
    )

    ok = await handler.perform_tag_review(
        owner="alice",
        repo_name="repo-a",
        from_tag="v1.0.0",
        to_tag="v1.1.0",
        trigger_type="manual",
        actor_username="alice",
    )
    assert ok is True, "perform_tag_review 应返回 True"
    assert gitea.statuses[0][1] == "pending", f"首个 status 应为 pending，实际 {gitea.statuses[0]}"
    # overall_severity="none" 且 summary 不含"严重/critical" → indicates_failure False → state=success
    final_state = gitea.statuses[-1][1]
    assert final_state == "success", (
        f"末个 status 应为 success，实际 {gitea.statuses[-1]}；"
        f"这说明 ReviewResult.indicates_failure 返回了 True（可能因 summary 含触发词）"
    )

    async with db.session() as session:
        rows = (await session.execute(text("SELECT kind, from_tag, to_tag, head_sha, status, overall_success FROM analysis_runs"))).all()
        assert len(rows) == 1
        r = rows[0]
        assert r[0] == "tag_review"
        assert r[1] == "v1.0.0"
        assert r[2] == "v1.1.0"
        assert r[3] == "sha-v1.1.0"
        assert r[4] == "completed"
        assert r[5] == 1

    # 幂等：再触发一次应跳过
    ok2 = await handler.perform_tag_review(
        owner="alice",
        repo_name="repo-a",
        from_tag="v1.0.0",
        to_tag="v1.1.0",
        trigger_type="manual",
        actor_username="alice",
    )
    assert ok2 is True
    async with db.session() as session:
        cnt = (await session.execute(text("SELECT COUNT(*) FROM analysis_runs"))).scalar()
        assert cnt == 1, f"幂等失败，应有 1 条记录，实际 {cnt}"

    await db.close()


def test_tag_review_end_to_end():
    asyncio.run(_run_tag_review_e2e())
