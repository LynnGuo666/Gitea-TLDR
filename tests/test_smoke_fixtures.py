"""阶段 6 冒烟测试：验证 in-memory sqlite fixture + Fake 替身能驱动真实
WebhookHandler 落库一条 analysis_run。

不追求覆盖 _perform_review 全部分支（阶段 7 完成），只确认测试网可用：
- `db` fixture 能 init + create_tables + session
- FakeGiteaClient / FakeRepoManager / StubReviewEngine 可注入 WebhookHandler
- `_perform_review` 在「配置缺失」分支能真实写一条 failed analysis_run 到 DB
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.review.webhook_handler import WebhookHandler
from app.services.db_service import DBService
from app.services.repositories import UsageRepository
from tests.fakes import FakeGiteaClient, FakeRepoManager, StubReviewEngine


def _pr_payload(**overrides: Any) -> Dict[str, Any]:
    base = {
        "action": "opened",
        "pull_request": {
            "number": 1,
            "title": "Test PR",
            "head": {"ref": "feat", "sha": "abc123"},
            "base": {"ref": "main"},
            "user": {"login": "alice"},
        },
        "repository": {
            "name": "repo-a",
            "owner": {"login": "alice"},
        },
        "sender": {"login": "alice"},
    }
    base.update(overrides)
    return base


def test_db_fixture_creates_tables_and_supports_session(db):
    """db fixture 应建好全部表，且 session 可写可读。"""

    async def _run():
        async with db.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_or_create_repository("alice", "repo-a")
            assert repo.id is not None
            # 再次 get 应命中同一条
            again = await db_service.get_repository("alice", "repo-a")
            assert again is not None and again.id == repo.id

    asyncio.run(_run())


def test_perform_review_configuration_required_writes_failed_run(db):
    """仓库无 review config 时，_perform_review 走 configuration_required 分支。

    行为：config 块在 DB session 内 raise RuntimeError，session 回滚（failed
    run 未持久化——这是当前生产行为，阶段 7 会单独覆盖），异常被外层 except
    捕获后返回 False。配置缺失发生在创建初始评论/拉 diff/克隆之前，因此
    Gitea 侧无任何副作用。
    """

    gitea = FakeGiteaClient()
    handler = WebhookHandler(
        gitea_client=gitea,
        repo_manager=FakeRepoManager(),
        review_engine=StubReviewEngine(),
        database=db,
    )

    pr_data = _pr_payload()["pull_request"]

    ok = asyncio.run(
        handler._perform_review(
            owner="alice",
            repo_name="repo-a",
            pr_number=1,
            pr_data=pr_data,
            features=["comment"],
            focus_areas=["quality"],
            trigger_type="auto",
            actor_username="alice",
        )
    )
    assert ok is False
    # 配置缺失分支在创建评论 / 拉 diff / 克隆之前就 raise，Gitea 无副作用
    assert gitea.create_issue_comment_calls == []
    assert gitea.create_commit_status_calls == []
    assert gitea.get_pull_request_diff_calls == []


def test_usage_repository_records_event_against_in_memory_db(db):
    """UsageRepository 在 in-memory DB 上能真实落一条 usage_event。"""

    async def _run():
        async with db.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_or_create_repository("alice", "repo-a")
            event = await UsageRepository(session).record_usage_event(
                repository_id=repo.id,
                input_tokens=10,
                output_tokens=5,
            )
            assert event.id is not None
            assert event.input_tokens == 10

    asyncio.run(_run())


def test_fake_gitea_client_records_calls():
    """FakeGiteaClient 应记录每次调用参数。"""
    client = FakeGiteaClient()
    asyncio.run(client.create_issue_comment("alice", "repo-a", 1, "hi"))
    asyncio.run(client.create_commit_status("alice", "repo-a", "sha", "pending"))
    assert client.create_issue_comment_calls[0]["body"] == "hi"
    assert client.commit_status_states == ["pending"]


def test_fake_repo_manager_no_op_clone_and_cleanup():
    """FakeRepoManager clone/cleanup 不启子进程，且记录调用。"""
    mgr = FakeRepoManager()
    path = asyncio.run(
        mgr.clone_repository("url", "alice", "repo-a", 1, "feat", auth_token="t")
    )
    assert path == mgr.clone_path
    assert mgr.clone_calls[0]["branch"] == "feat"
    mgr.cleanup_repository("alice", "repo-a", 1)
    assert mgr.cleanup_calls[0]["pr_number"] == 1


def test_stub_engine_returns_configured_result():
    """StubReviewEngine 返回预设 ReviewResult。"""
    from tests.fakes import make_review_result

    result = make_review_result()
    engine = StubReviewEngine(result=result)
    out = asyncio.run(
        engine.analyze_pr(Path("/x"), "diff", ["quality"], {}, api_url="u")
    )
    assert out is result
    assert engine.analyze_pr_calls[0]["api_url"] == "u"
