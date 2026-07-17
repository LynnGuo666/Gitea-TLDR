"""`_perform_review` 及 WebhookHandler 路由层端到端测试（阶段 7）。

用阶段 6 的 in-memory sqlite + Fake 替身组装真实 WebhookHandler，覆盖：
- 成功路径：analysis_run completed / provider_run completed / usage_event 落库 /
  Gitea create_review + create_commit_status 被调用 / annotations 保存
- 失败路径：analyze_pr 返回 None → status=failed / commit status failure
- 异常路径：analyze_pr raise → except 分支 → status=failed / return False
- 幂等保护：同 head_sha 的 completed run 命中 get_review_run_by_head 直接 return True
- 配置缺失：仓库无 review config → configuration_required
- 凭证缺失：config 有但 credential 无/inactive → credential_unavailable
- 空 diff：get_pull_request_diff 返回空 → failed
- 克隆失败：FakeRepoManager.fail_clone → failed
- /review 命令解析：handle_issue_comment PR 评论路由到 _perform_review，参数透传
- _process_with_retry 重试状态机：handler 失败 → WebhookLog retrying→error
- bot 自触发过滤：_is_bot_actor 命中 → 跳过
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import settings
from app.models import (
    AnalysisAnnotation,
    AnalysisRun,
    ProviderRun,
    WebhookEvent,
    WEBHOOK_STATUS_ERROR,
)
from app.review.providers.base import InlineComment
from app.review.webhook_handler import WebhookHandler
from app.services.db_service import DBService
from tests.fakes import (
    FakeGiteaClient,
    FakeRepoManager,
    StubReviewEngine,
    make_review_result,
)

OWNER = "alice"
REPO = "repo-a"
PR_NUMBER = 1
HEAD_SHA = "abc123def456"
HEAD_BRANCH = "feat"
BASE_BRANCH = "main"


# ---------------------------------------------------------------------------
# Payload / DB seed 辅助
# ---------------------------------------------------------------------------


def _pr_payload(
    *,
    action: str = "opened",
    sender: str = "alice",
    head_sha: str = HEAD_SHA,
) -> Dict[str, Any]:
    return {
        "action": action,
        "pull_request": {
            "number": PR_NUMBER,
            "title": "Test PR",
            "head": {"ref": HEAD_BRANCH, "sha": head_sha},
            "base": {"ref": BASE_BRANCH, "sha": "xyz789"},
            "user": {"login": "alice"},
        },
        "repository": {
            "name": REPO,
            "owner": {"login": OWNER},
        },
        "sender": {"login": sender},
    }


def _comment_payload(
    *,
    body: str,
    sender: str = "alice",
    pr_number: int = PR_NUMBER,
    comment_id: int = 555,
) -> Dict[str, Any]:
    return {
        "action": "created",
        "comment": {"id": comment_id, "body": body, "user": {"login": sender}},
        "issue": {
            "number": pr_number,
            "pull_request": {"url": "https://git.example.com/api/v1/repos/.../pulls/1"},
        },
        "repository": {
            "name": REPO,
            "owner": {"login": OWNER},
        },
        "sender": {"login": sender},
    }


def seed_review_config(
    db,
    *,
    owner: str = OWNER,
    repo_name: str = REPO,
    engine: str = "forge",
    model: Optional[str] = "claude-sonnet-4-20250514",
    api_key: Optional[str] = "sk-test",
    api_url: Optional[str] = "https://api.anthropic.com",
    active_credential: bool = True,
    focus: Optional[list[str]] = None,
    features: Optional[list[str]] = None,
) -> int:
    """直接通过 ORM 插入 repo + credential + review config，返回 repository_id。

    production 创建路径分散且耦合路由层；测试直接组装 ORM 实体更可控。
    """

    async def _seed():
        async with db.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_or_create_repository(owner, repo_name)
            cred = await db_service.create_provider_credential(
                name="test-cred",
                provider=engine,
                api_url=api_url,
                api_key=api_key,
            )
            if not active_credential:
                cred.is_active = False
                await session.flush()

            from app.models import RepositoryConfig

            cfg = RepositoryConfig(
                repository_id=repo.id,
                scenario="review",
                engine=engine,
                model=model,
                credential_id=cred.id,
                wire_api=None,
                is_active=True,
            )
            cfg.set_focus(focus or ["quality", "security"])
            cfg.set_features(features or ["comment", "review", "status"])
            session.add(cfg)
            await session.flush()
            return repo.id

    return asyncio.run(_seed())


def _build_handler(
    db,
    *,
    gitea: Optional[FakeGiteaClient] = None,
    repo_manager: Optional[FakeRepoManager] = None,
    engine: Optional[StubReviewEngine] = None,
    bot_username: Optional[str] = None,
) -> tuple[WebhookHandler, FakeGiteaClient, FakeRepoManager, StubReviewEngine]:
    gitea = gitea or FakeGiteaClient()
    repo_manager = repo_manager or FakeRepoManager()
    engine = engine or StubReviewEngine()
    handler = WebhookHandler(
        gitea_client=gitea,
        repo_manager=repo_manager,
        review_engine=engine,
        database=db,
        bot_username=bot_username,
    )
    return handler, gitea, repo_manager, engine


def _perform(handler, **kwargs):
    """同步驱动 _perform_review。"""
    defaults = dict(
        owner=OWNER,
        repo_name=REPO,
        pr_number=PR_NUMBER,
        pr_data=_pr_payload()["pull_request"],
        features=["comment", "review", "status"],
        focus_areas=["quality"],
        trigger_type="auto",
        actor_username="alice",
    )
    defaults.update(kwargs)
    return asyncio.run(handler._perform_review(**defaults))


# ---------------------------------------------------------------------------
# 成功路径
# ---------------------------------------------------------------------------


def test_success_path_completes_run_and_publishes(db):
    """成功路径：analysis_run completed、provider_run completed、usage_event 落库、
    Gitea create_review + create_commit_status(success) 被调用、annotations 保存。"""
    seed_review_config(db)
    result = make_review_result(
        summary="## 审查发现\n\n- 文件 file.py 第 10 行有空指针风险",
        overview="## 变更概览\n\n新增逻辑",
        inline_comments=[
            InlineComment(
                path="file.py",
                new_line=10,
                severity="medium",
                comment="空指针风险",
                suggestion="加 None 判断",
            )
        ],
        overall_severity="medium",
        usage={
            "input_tokens": 120,
            "output_tokens": 80,
            "model": "claude-sonnet-4-20250514",
        },
    )
    handler, gitea, repo_mgr, engine = _build_handler(
        db, engine=StubReviewEngine(result=result)
    )

    ok = _perform(handler)
    assert ok is True

    # 克隆被调用且清理过
    assert len(repo_mgr.clone_calls) == 1
    assert len(repo_mgr.cleanup_calls) == 1

    # 初始评论 + 概览更新 + 审查发现评论
    assert len(gitea.create_issue_comment_calls) >= 2
    assert len(gitea.update_issue_comment_calls) == 1
    # review 与 status 被调用
    assert len(gitea.create_review_calls) == 1
    assert gitea.create_review_calls[0]["commit_id"] == HEAD_SHA
    assert "success" in gitea.commit_status_states  # pending + success
    # 引擎收到正确参数
    assert engine.analyze_pr_calls[0]["api_key"] == "sk-test"
    assert engine.analyze_pr_calls[0]["engine"] == "forge"

    async def _verify_db():
        async with db.session() as session:
            from sqlalchemy import select

            run = (
                await session.execute(
                    select(AnalysisRun).where(AnalysisRun.kind == "review")
                )
            ).scalar_one()
            assert run.status == "completed"
            assert run.overall_success is True
            assert run.overall_severity == "medium"

            anns = list(
                (
                    await session.execute(
                        select(AnalysisAnnotation).where(
                            AnalysisAnnotation.analysis_run_id == run.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(anns) == 1
            assert anns[0].file_path == "file.py"

            prun = (await session.execute(select(ProviderRun))).scalar_one()
            assert prun.status == "completed"

            from app.models import UsageEvent

            usage = (await session.execute(select(UsageEvent))).scalar_one()
            assert usage.input_tokens == 120
            assert usage.output_tokens == 80

    asyncio.run(_verify_db())


# ---------------------------------------------------------------------------
# 失败路径（analyze_pr 返回 None）
# ---------------------------------------------------------------------------


def test_failure_path_analyze_returns_none(db):
    """analyze_pr 返回 None → status=failed、commit status failure、失败评论发布。"""
    seed_review_config(db)
    handler, gitea, _repo_mgr, engine = _build_handler(
        db, engine=StubReviewEngine(result=None, last_error="模型超时")
    )

    ok = _perform(handler)
    assert ok is False

    assert "error" in gitea.commit_status_states
    assert len(gitea.update_issue_comment_calls) == 1
    assert "模型超时" in gitea.update_issue_comment_calls[0]["body"]

    async def _verify():
        async with db.session() as session:
            from sqlalchemy import select

            run = (
                await session.execute(
                    select(AnalysisRun).where(AnalysisRun.kind == "review")
                )
            ).scalar_one()
            assert run.status == "failed"
            assert run.overall_success is False

            prun = (await session.execute(select(ProviderRun))).scalar_one()
            assert prun.status == "failed"

    asyncio.run(_verify())


# ---------------------------------------------------------------------------
# 异常路径（analyze_pr raise）
# ---------------------------------------------------------------------------


def test_exception_path_analyze_raises(db):
    """analyze_pr raise → except 分支 → status=failed、return False。"""
    seed_review_config(db)
    handler, _gitea, _repo_mgr, _engine = _build_handler(
        db, engine=StubReviewEngine(raise_on_call=RuntimeError("boom"))
    )

    ok = _perform(handler)
    assert ok is False

    async def _verify():
        async with db.session() as session:
            from sqlalchemy import select

            run = (
                await session.execute(
                    select(AnalysisRun).where(AnalysisRun.kind == "review")
                )
            ).scalar_one()
            assert run.status == "failed"
            assert "boom" in (run.error_message or "")

            prun = (await session.execute(select(ProviderRun))).scalar_one()
            assert prun.status == "failed"

    asyncio.run(_verify())


# ---------------------------------------------------------------------------
# 幂等保护
# ---------------------------------------------------------------------------


def test_idempotent_skips_existing_completed_run(db):
    """预先插入同 head_sha 的 completed run → 命中 get_review_run_by_head 直接 return True，
    不重复审查（Gitea 无副作用、引擎不被调用）。"""
    repo_id = seed_review_config(db)

    async def _seed_existing():
        async with db.session() as session:
            db_service = DBService(session)
            run = await db_service.create_analysis_run(
                kind="review",
                repository_id=repo_id,
                external_number=PR_NUMBER,
                trigger_type="auto",
                head_sha=HEAD_SHA,
            )
            await db_service.complete_analysis_run(
                run.id, status="completed", overall_success=True
            )

    asyncio.run(_seed_existing())

    result = make_review_result()
    handler, gitea, repo_mgr, engine = _build_handler(
        db, engine=StubReviewEngine(result=result)
    )
    ok = _perform(handler)
    assert ok is True
    # 幂等：未克隆、未调引擎、未发评论
    assert repo_mgr.clone_calls == []
    assert engine.analyze_pr_calls == []
    assert gitea.create_issue_comment_calls == []


# ---------------------------------------------------------------------------
# 配置缺失 / 凭证缺失
# ---------------------------------------------------------------------------


def test_configuration_required_when_no_config(db):
    """仓库无 review config → configuration_required，Gitea 无副作用。"""

    # 只建 repo，不建 config
    async def _seed_repo():
        async with db.session() as session:
            await DBService(session).get_or_create_repository(OWNER, REPO)

    asyncio.run(_seed_repo())

    handler, gitea, repo_mgr, engine = _build_handler(db)
    ok = _perform(handler)
    assert ok is False
    assert gitea.create_issue_comment_calls == []
    assert repo_mgr.clone_calls == []
    assert engine.analyze_pr_calls == []


def test_credential_unavailable_when_credential_inactive(db):
    """config 有但 credential inactive → credential_unavailable，Gitea 无副作用。"""
    seed_review_config(db, active_credential=False)
    handler, gitea, repo_mgr, engine = _build_handler(db)
    ok = _perform(handler)
    assert ok is False
    assert gitea.create_issue_comment_calls == []
    assert repo_mgr.clone_calls == []
    assert engine.analyze_pr_calls == []


# ---------------------------------------------------------------------------
# 空 diff / 克隆失败
# ---------------------------------------------------------------------------


def test_empty_diff_fails(db):
    """get_pull_request_diff 返回空 → failed。"""
    seed_review_config(db)
    gitea = FakeGiteaClient(diff_content="")
    handler, gitea, repo_mgr, engine = _build_handler(db, gitea=gitea)
    ok = _perform(handler)
    assert ok is False
    # 未克隆（diff 为空在克隆前就 return False）
    assert repo_mgr.clone_calls == []
    assert engine.analyze_pr_calls == []


def test_clone_failure_fails(db):
    """FakeRepoManager.fail_clone → failed。"""
    seed_review_config(db)
    handler, _gitea, _repo_mgr, engine = _build_handler(
        db, repo_manager=FakeRepoManager(fail_clone=True)
    )
    ok = _perform(handler)
    assert ok is False
    assert engine.analyze_pr_calls == []

    async def _verify():
        async with db.session() as session:
            from sqlalchemy import select

            run = (
                await session.execute(
                    select(AnalysisRun).where(AnalysisRun.kind == "review")
                )
            ).scalar_one()
            assert run.status == "failed"

    asyncio.run(_verify())


# ---------------------------------------------------------------------------
# /review 命令解析（handle_issue_comment）
# ---------------------------------------------------------------------------


def test_handle_issue_comment_routes_review_command(db, monkeypatch):
    """PR 评论 /review --features comment --focus security → 路由到 _perform_review，
    参数透传正确。"""
    seed_review_config(db)
    result = make_review_result()
    handler, gitea, _repo_mgr, engine = _build_handler(
        db,
        gitea=FakeGiteaClient(
            pr_data=_pr_payload()["pull_request"],
        ),
        engine=StubReviewEngine(result=result),
    )

    payload = _comment_payload(body="/review --features comment --focus security")
    ok = asyncio.run(handler.handle_issue_comment(payload))
    assert ok is True

    # 引擎收到的 focus_areas 应来自命令参数（security）
    assert engine.analyze_pr_calls[0]["focus_areas"] == ["security"]


def test_handle_issue_comment_ignores_non_review_command_on_pr(db):
    """PR 评论中非 /review 命令被忽略，返回 True 不触发审查。"""
    seed_review_config(db)
    handler, gitea, _repo_mgr, engine = _build_handler(db)
    payload = _comment_payload(body="/issue --focus bug")
    ok = asyncio.run(handler.handle_issue_comment(payload))
    assert ok is True
    assert engine.analyze_pr_calls == []


def test_handle_issue_comment_ignores_non_created_action(db):
    """action != created 的评论事件被忽略。"""
    seed_review_config(db)
    handler, _gitea, _repo_mgr, engine = _build_handler(db)
    payload = _comment_payload(body="/review")
    payload["action"] = "edited"
    ok = asyncio.run(handler.handle_issue_comment(payload))
    assert ok is True
    assert engine.analyze_pr_calls == []


# ---------------------------------------------------------------------------
# _process_with_retry 重试状态机
# ---------------------------------------------------------------------------


def test_process_with_retry_records_retry_then_error(db, monkeypatch):
    """handler_func 抛异常 → WebhookLog status 经 retrying 最终 error，retry_count 递增。

    _perform_review 内部捕获引擎异常后返回 False（不抛），所以重试路径要靠
    handler_func 自身抛异常来驱动——这里用一个始终 raise 的 handler_func。
    用 monkeypatch 把 asyncio.sleep 改成 no-op，避免真实退避等待。
    """
    seed_review_config(db)
    handler, _gitea, _repo_mgr, _engine = _build_handler(db)

    async def _noop_sleep(*_a, **_k):
        return None

    monkeypatch.setattr("asyncio.sleep", _noop_sleep)

    payload = _pr_payload()
    call_count = {"n": 0}

    async def _always_raise():
        call_count["n"] += 1
        raise RuntimeError("always fail")

    async def _run():
        await handler._process_with_retry(
            payload=payload,
            event_type="pull_request",
            handler_func=_always_raise,
            max_retries=2,
            base_delay=0.01,
        )

    asyncio.run(_run())
    # max_retries=2 → 共 3 次尝试
    assert call_count["n"] == 3

    async def _verify():
        async with db.session() as session:
            from sqlalchemy import select

            log = (await session.execute(select(WebhookEvent))).scalar_one()
            assert log.status == WEBHOOK_STATUS_ERROR
            assert log.retry_count >= 2

    asyncio.run(_verify())


def test_process_with_retry_success_on_first_try(db, monkeypatch):
    """handler 首次成功 → WebhookLog status=success。"""
    seed_review_config(db)
    result = make_review_result()
    handler, _g, _rm, _e = _build_handler(db, engine=StubReviewEngine(result=result))
    payload = _pr_payload()

    async def _run():
        await handler._process_with_retry(
            payload=payload,
            event_type="pull_request",
            handler_func=lambda: handler.handle_pull_request(
                payload, ["comment"], ["quality"]
            ),
            max_retries=2,
            base_delay=0.01,
        )

    asyncio.run(_run())

    async def _verify():
        async with db.session() as session:
            from sqlalchemy import select

            log = (await session.execute(select(WebhookEvent))).scalar_one()
            from app.models import WEBHOOK_STATUS_SUCCESS

            assert log.status == WEBHOOK_STATUS_SUCCESS
            assert log.retry_count == 0

    asyncio.run(_verify())


# ---------------------------------------------------------------------------
# bot 自触发过滤
# ---------------------------------------------------------------------------


def test_bot_self_trigger_pr_is_skipped(db, monkeypatch):
    """PR 作者或 sender 是 bot → 跳过，返回 True 不审查。"""
    seed_review_config(db)
    # 让 settings.bot_username 命中 sender
    monkeypatch.setattr(settings, "bot_username", "pr-reviewer-bot")
    result = make_review_result()
    handler, _g, repo_mgr, engine = _build_handler(
        db, engine=StubReviewEngine(result=result), bot_username="pr-reviewer-bot"
    )
    payload = _pr_payload(sender="pr-reviewer-bot")
    ok = asyncio.run(handler.handle_pull_request(payload, ["comment"], ["quality"]))
    assert ok is True
    assert repo_mgr.clone_calls == []
    assert engine.analyze_pr_calls == []


def test_bot_self_comment_is_ignored(db, monkeypatch):
    """bot 自发评论中的命令被忽略。"""
    seed_review_config(db)
    monkeypatch.setattr(settings, "bot_username", "pr-reviewer-bot")
    handler, _g, _rm, engine = _build_handler(db, bot_username="pr-reviewer-bot")
    payload = _comment_payload(body="/review", sender="pr-reviewer-bot")
    ok = asyncio.run(handler.handle_issue_comment(payload))
    assert ok is True
    assert engine.analyze_pr_calls == []


def test_non_opened_pr_action_ignored(db):
    """非 opened/synchronized 的 PR 事件被忽略。"""
    seed_review_config(db)
    handler, _g, repo_mgr, engine = _build_handler(db)
    payload = _pr_payload(action="closed")
    ok = asyncio.run(handler.handle_pull_request(payload, ["comment"], ["quality"]))
    assert ok is True
    assert repo_mgr.clone_calls == []
    assert engine.analyze_pr_calls == []
