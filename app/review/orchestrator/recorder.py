"""DB 写入协调类（拆分自 _perform_review 原 DB 块 + :961-1043）。

封装 analysis_run / provider_run / annotations / usage_event 的创建与收尾，
让 orchestrator 不再直接操作 DBService 细节。
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any, Dict, List, Optional

from app.services.db_service import DBService
from app.services.repositories import UsageRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RunRecorder:
    """协调一次审查运行的 DB 写入。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.db_service = DBService(session)

    async def create_run(
        self,
        *,
        repository_id: int,
        pr_number: int,
        pr_data: Dict[str, Any],
        trigger_type: str,
        engine: str,
        model: Optional[str],
        repo_config: Any,
        head_sha: Optional[str],
        focus_areas: List[str],
        features: List[str],
        config_source: str,
    ) -> int:
        """创建 analysis_run，返回 run_id。"""
        run = await self.db_service.create_analysis_run(
            kind="review",
            repository_id=repository_id,
            external_number=pr_number,
            trigger_type=trigger_type,
            effective_engine=engine,
            effective_model=model,
            repository_config_id=repo_config.id,
            credential_id=repo_config.credential_id,
            external_title=pr_data.get("title"),
            external_author=pr_data.get("user", {}).get("login"),
            source_branch=pr_data.get("head", {}).get("ref"),
            target_branch=pr_data.get("base", {}).get("ref"),
            head_sha=head_sha,
            result_payload={
                "enabled_features": features,
                "focus_areas": focus_areas,
                "config_source": config_source,
            },
        )
        return run.id

    async def fail_run(
        self,
        run_id: Optional[int],
        *,
        error_message: str,
        analysis_mode: Optional[str] = None,
        diff_size: int = 0,
        config_source: Optional[str] = None,
    ) -> None:
        if run_id is None:
            return
        payload: Optional[Dict[str, Any]] = None
        if analysis_mode is not None or config_source is not None:
            payload = {
                "analysis_mode": analysis_mode,
                "diff_size_bytes": diff_size,
                "config_source": config_source,
            }
        await self.db_service.complete_analysis_run(
            run_id,
            status="failed",
            overall_success=False,
            result_payload=payload,
            error_message=error_message,
        )

    async def complete_run(
        self,
        run_id: int,
        *,
        success: bool,
        analysis_result: Any,
        diff_size: int,
        analysis_mode: Optional[str],
        config_source: str,
        features: List[str],
        focus_areas: List[str],
    ) -> None:
        """成功收尾 analysis_run 并保存行级 annotations。"""
        summary_markdown = analysis_result.summary_text() or "未生成审查报告"
        await self.db_service.complete_analysis_run(
            run_id,
            status="completed" if success else "failed",
            overall_severity=analysis_result.overall_severity,
            summary_markdown=summary_markdown,
            overall_success=success,
            result_payload={
                "config_source": config_source,
                "analysis_mode": analysis_mode,
                "diff_size_bytes": diff_size,
                "inline_comments_count": len(analysis_result.inline_comments),
                "enabled_features": features,
                "focus_areas": focus_areas,
            },
        )

        if analysis_result.inline_comments:
            comments_data = [
                {
                    "path": c.path,
                    "new_line": c.new_line,
                    "old_line": c.old_line,
                    "severity": c.severity,
                    "comment": c.comment,
                    "suggestion": c.suggestion,
                }
                for c in analysis_result.inline_comments
            ]
            await self.db_service.save_analysis_annotations(run_id, comments_data)

    async def record_usage(
        self,
        *,
        repository_id: int,
        analysis_run_id: int,
        actor_user_id: Optional[int],
        analysis_result: Any,
        gitea_api_calls: int,
        clone_operations: int,
    ) -> None:
        meta = analysis_result.usage_metadata
        await UsageRepository(self.session).record_usage_event(
            repository_id=repository_id,
            analysis_run_id=analysis_run_id,
            user_id=actor_user_id,
            input_tokens=meta.get("input_tokens", 0),
            output_tokens=meta.get("output_tokens", 0),
            cache_creation_input_tokens=meta.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=meta.get("cache_read_input_tokens", 0),
            gitea_api_calls=gitea_api_calls,
            provider_api_calls=1,
            clone_operations=clone_operations,
        )

    async def create_provider_run(
        self,
        *,
        repository_id: int,
        engine: str,
        analysis_run_id: Optional[int],
    ) -> Optional[str]:
        """创建 ProviderRun（status=running），返回 session_id；失败返回 None（非致命）。"""
        try:
            run = await self.db_service.create_provider_run(
                repository_id,
                "review",
                provider=engine,
                analysis_run_id=analysis_run_id,
            )
            return run.session_id
        except Exception as exc:
            logger.warning("创建 ProviderRun 失败（非致命）: %s", exc)
            return None

    async def complete_provider_run(
        self,
        provider_run_session_id: Optional[str],
        *,
        status: str,
        analysis_result: Any = None,
        model: Optional[str] = None,
        error: Optional[str] = None,
        analysis_run_id: Optional[int] = None,
    ) -> None:
        if not provider_run_session_id:
            return
        try:
            if status == "completed" and analysis_result is not None:
                meta = analysis_result.usage_metadata
                _msgs = meta.get("forge_messages") or []
                await self.db_service.complete_provider_run(
                    provider_run_session_id,
                    status="completed",
                    model=meta.get("model") or model,
                    turns=meta.get("turns", 0),
                    tool_calls_count=meta.get("tool_calls", 0),
                    messages_json=_json.dumps(_msgs, ensure_ascii=False)
                    if _msgs
                    else None,
                    input_tokens=meta.get("input_tokens", 0),
                    output_tokens=meta.get("output_tokens", 0),
                    cache_creation_input_tokens=meta.get(
                        "cache_creation_input_tokens", 0
                    ),
                    cache_read_input_tokens=meta.get("cache_read_input_tokens", 0),
                    analysis_run_id=analysis_run_id,
                )
            else:
                await self.db_service.complete_provider_run(
                    provider_run_session_id,
                    status=status,
                    model=model,
                    analysis_run_id=analysis_run_id,
                    error=error,
                )
        except Exception as exc:
            logger.warning("完成 ProviderRun 失败（非致命）: %s", exc)
