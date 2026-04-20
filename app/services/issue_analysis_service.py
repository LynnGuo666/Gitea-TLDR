"""
Issue 分析服务
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional

try:  # jieba 为中文分词提供支持，未安装时退化成纯英文正则
    import jieba  # type: ignore

    _JIEBA_AVAILABLE = True
except Exception:  # pragma: no cover - 仅在依赖缺失时触发
    jieba = None  # type: ignore[assignment]
    _JIEBA_AVAILABLE = False

from app.core import settings
from app.core.database import Database
from app.models import DEFAULT_ISSUE_FOCUS
from app.services.db_service import DBService
from app.services.gitea_client import GiteaClient
from app.services.issue_config_resolver import (
    ResolvedIssueConfig,
    resolve_issue_config,
)
from app.services.providers.base import IssueResult
from app.services.providers.forge.provider import (
    DEFAULT_FORGE_BASE_URL,
    DEFAULT_FORGE_MODEL,
    ForgeProvider,
)
from app.services.repo_manager import RepoManager

logger = logging.getLogger(__name__)

SIMILAR_ISSUE_LIMIT = 5
SIMILAR_ISSUE_FETCH_LIMIT = 100
WORKSPACE_KIND = "issue"
DUPLICATE_WINDOW_SECONDS = 300  # 5 分钟内拒绝重复成功分析
AI_ANALYZED_LABEL = "ai-analyzed"
POSSIBLE_DUPLICATE_LABEL = "possibly-duplicate"
AI_ANALYZED_LABEL_COLOR = "#0ea5e9"
POSSIBLE_DUPLICATE_LABEL_COLOR = "#f97316"

_STOP_WORDS = {
    "issue",
    "issues",
    "error",
    "bug",
    "problem",
    "question",
    "the",
    "and",
    "with",
    "that",
    "for",
    "this",
    "have",
    "has",
    "are",
    "was",
    "were",
    "from",
    "问题",
    "错误",
    "异常",
    "报错",
    "现象",
    "复现",
    "描述",
    "如何",
    "怎么",
    "为什么",
    "请问",
    "是",
    "了",
    "的",
    "在",
    "有",
    "不",
    "这",
    "我",
    "你",
    "他",
    "一个",
    "可以",
    "使用",
    "出现",
}


class IssueAnalysisService:
    """负责编排 Issue 分析主链路。"""

    def __init__(
        self,
        gitea_client: GiteaClient,
        repo_manager: RepoManager,
        database: Optional[Database] = None,
    ):
        self.gitea_client = gitea_client
        self.repo_manager = repo_manager
        self.database = database

    async def analyze_issue(
        self,
        payload: Dict[str, Any],
        *,
        trigger_type: str,
        source_comment_id: Optional[int] = None,
        actor_username: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
    ) -> bool:
        """分析普通 Issue。"""
        issue_session_id: Optional[int] = None
        repository_id: Optional[int] = None
        actor_user_id: Optional[int] = None
        gitea_api_calls = 0
        clone_operations = 0
        bot_comment_id: Optional[int] = None
        issue_data = payload.get("issue", {})
        repo_data = payload.get("repository", {})

        owner = repo_data.get("owner", {}).get("login") or repo_data.get("owner", {}).get("username")
        repo_name = repo_data.get("name")
        issue_number = issue_data.get("number")
        issue_title = issue_data.get("title")
        issue_author = issue_data.get("user", {}).get("login")
        issue_state = issue_data.get("state")

        if not owner or not repo_name or not issue_number:
            logger.error("Issue payload 缺少必要字段")
            return False

        logger.info(
            "执行 Issue 分析: %s/%s#%s (trigger=%s)",
            owner,
            repo_name,
            issue_number,
            trigger_type,
        )

        # 幂等保护（只有在数据库可用时才检查，避免测试环境行为偏差）
        if self.database:
            async with self.database.session() as session:
                db_service = DBService(session)
                repo = await db_service.get_repository(owner, repo_name)
                if repo:
                    in_flight = await db_service.get_in_flight_issue_session(
                        repo.id, issue_number
                    )
                    if in_flight:
                        logger.info(
                            "跳过重复 Issue 分析（in-flight）: %s/%s#%s session=%s",
                            owner,
                            repo_name,
                            issue_number,
                            in_flight.id,
                        )
                        return True
                    recent = await db_service.get_recent_successful_issue_session(
                        repo.id, issue_number, DUPLICATE_WINDOW_SECONDS
                    )
                    if recent:
                        logger.info(
                            "跳过重复 Issue 分析（最近 %ss 内成功）: %s/%s#%s session=%s",
                            DUPLICATE_WINDOW_SECONDS,
                            owner,
                            repo_name,
                            issue_number,
                            recent.id,
                        )
                        return True

        try:
            (
                repository_id,
                actor_user_id,
                issue_session_id,
                resolved_config,
                config_source,
                effective_focus,
            ) = await self._prepare_session(
                owner=owner,
                repo_name=repo_name,
                issue_number=issue_number,
                issue_title=issue_title,
                issue_author=issue_author,
                issue_state=issue_state,
                trigger_type=trigger_type,
                source_comment_id=source_comment_id,
                actor_username=actor_username,
                focus_areas=focus_areas,
            )

            placeholder_body = self._build_placeholder_comment(trigger_type)
            bot_comment_id = await self.gitea_client.create_issue_comment(
                owner, repo_name, issue_number, placeholder_body
            )
            gitea_api_calls += 1

            if self.database and issue_session_id and bot_comment_id is not None:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    await db_service.update_issue_session(
                        issue_session_id,
                        bot_comment_id=bot_comment_id,
                    )

            if (resolved_config.engine or "forge") != "forge":
                logger.warning(
                    "Issue 引擎 %s 暂未支持，回退到 forge",
                    resolved_config.engine,
                )

            resolved_api_key = resolved_config.api_key or ""
            if not resolved_api_key:
                raise RuntimeError(
                    "Forge: 未配置 API Key（FORGE_API_KEY 或仓库级 Issue api_key）"
                )

            similar_issue_candidates = await self._find_similar_issue_candidates(
                owner,
                repo_name,
                issue_data,
            )
            gitea_api_calls += 1

            clone_url = self.gitea_client.get_clone_url(owner, repo_name)
            default_branch = (
                repo_data.get("default_branch")
                or issue_data.get("repository", {}).get("default_branch")
                or "main"
            )
            repo_path = await self.repo_manager.clone_workspace(
                clone_url=clone_url,
                owner=owner,
                repo=repo_name,
                workspace_kind=WORKSPACE_KIND,
                workspace_id=issue_number,
                branch=default_branch,
                auth_token=self.gitea_client.token,
            )

            if not repo_path:
                raise RuntimeError("无法克隆仓库默认分支，Issue 分析中止")

            clone_operations += 1

            provider = ForgeProvider()
            result: Optional[IssueResult] = await provider.analyze_issue(
                repo_path=repo_path,
                issue_info=issue_data,
                similar_candidates=similar_issue_candidates,
                api_url=resolved_config.api_url or DEFAULT_FORGE_BASE_URL,
                api_key=resolved_api_key,
                model=resolved_config.model or DEFAULT_FORGE_MODEL,
                custom_prompt=resolved_config.custom_prompt,
                focus_areas=effective_focus,
                temperature=resolved_config.temperature,
                max_tokens=resolved_config.max_tokens,
                max_turns=max(1, int(getattr(settings, "forge_max_turns", 5) or 5)),
            )

            self.repo_manager.cleanup_workspace(
                owner, repo_name, WORKSPACE_KIND, issue_number
            )

            if result is None:
                error_text = provider.last_error or "Issue 分析未返回结果"
                raise RuntimeError(error_text)

            analysis_payload = result.structured_data
            comment_body = self._build_result_comment(
                analysis_payload, fallback_mode=result.fallback_mode
            )

            success = True
            if bot_comment_id:
                success = await self.gitea_client.update_issue_comment(
                    owner, repo_name, bot_comment_id, comment_body
                )
            else:
                new_comment_id = await self.gitea_client.create_issue_comment(
                    owner, repo_name, issue_number, comment_body
                )
                bot_comment_id = new_comment_id
                success = new_comment_id is not None
            gitea_api_calls += 1

            # 成功后自动打 label（非致命错误，失败不影响主流程）
            if success and result.fallback_mode != "raw_text":
                gitea_api_calls += await self._apply_issue_labels(
                    owner, repo_name, issue_number, analysis_payload
                )

            if self.database and issue_session_id and repository_id:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    await db_service.update_issue_session(
                        issue_session_id,
                        engine=resolved_config.engine or "forge",
                        model=result.model,
                        config_source=config_source,
                        issue_state=issue_state,
                        bot_comment_id=bot_comment_id,
                        overall_severity=analysis_payload.get("overall_severity"),
                        summary_markdown=analysis_payload.get("summary_markdown", ""),
                        analysis_payload={
                            **analysis_payload,
                            "fallback_mode": result.fallback_mode,
                            "focus_areas": effective_focus,
                        },
                        overall_success=success,
                        completed=True,
                    )
                    usage = result.usage_metadata
                    await db_service.record_usage(
                        repository_id=repository_id,
                        issue_session_id=issue_session_id,
                        user_id=actor_user_id,
                        estimated_input_tokens=usage.get("input_tokens", 0),
                        estimated_output_tokens=usage.get("output_tokens", 0),
                        cache_creation_input_tokens=usage.get(
                            "cache_creation_input_tokens", 0
                        ),
                        cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                        gitea_api_calls=gitea_api_calls,
                        provider_api_calls=1,
                        clone_operations=clone_operations,
                    )

            logger.info("Issue 分析完成: %s/%s#%s", owner, repo_name, issue_number)
            return success
        except Exception as e:
            logger.error("Issue 分析失败: %s/%s#%s", owner, repo_name, issue_number, exc_info=True)
            if self.repo_manager:
                self.repo_manager.cleanup_workspace(owner, repo_name, WORKSPACE_KIND, issue_number)

            failure_body = self._build_failure_comment(str(e))
            if bot_comment_id:
                await self.gitea_client.update_issue_comment(
                    owner, repo_name, bot_comment_id, failure_body
                )
            else:
                await self.gitea_client.create_issue_comment(
                    owner, repo_name, issue_number, failure_body
                )

            if self.database and issue_session_id:
                try:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.update_issue_session(
                            issue_session_id,
                            overall_success=False,
                            error_message=str(e),
                            completed=True,
                        )
                except Exception as db_error:
                    logger.error("更新 Issue 分析会话失败: %s", db_error)
            return False

    async def _prepare_session(
        self,
        *,
        owner: str,
        repo_name: str,
        issue_number: int,
        issue_title: Optional[str],
        issue_author: Optional[str],
        issue_state: Optional[str],
        trigger_type: str,
        source_comment_id: Optional[int],
        actor_username: Optional[str],
        focus_areas: Optional[List[str]],
    ) -> tuple[int, Optional[int], Optional[int], ResolvedIssueConfig, str, List[str]]:
        repository_id = 0
        actor_user_id: Optional[int] = None
        issue_session_id: Optional[int] = None

        default_engine = (
            getattr(settings, "default_provider", None) or "forge"
        )

        base_resolved = ResolvedIssueConfig(
            inherit_global=True,
            engine=default_engine,
            model=getattr(settings, "forge_model", DEFAULT_FORGE_MODEL),
            api_url=getattr(settings, "forge_base_url", DEFAULT_FORGE_BASE_URL),
            api_key=getattr(settings, "forge_api_key", "") or None,
            wire_api=None,
            temperature=None,
            max_tokens=None,
            custom_prompt=None,
            default_focus=list(DEFAULT_ISSUE_FOCUS),
        )
        config_source = "global_default"

        if not self.database:
            effective_focus = list(focus_areas or base_resolved.default_focus)
            return (
                repository_id,
                actor_user_id,
                issue_session_id,
                base_resolved,
                config_source,
                effective_focus,
            )

        async with self.database.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_or_create_repository(owner, repo_name)
            repository_id = repo.id

            if actor_username:
                actor_user = await db_service.get_or_create_user_by_username(actor_username)
                actor_user_id = actor_user.id

            repo_issue_config = await db_service.get_repo_specific_issue_config(
                repository_id
            )
            global_issue_config = await db_service.get_global_issue_config()
            resolved = resolve_issue_config(
                repo_issue_config,
                global_issue_config,
                default_engine=default_engine,
            )
            # 环境默认值兜底，避免 resolver 完全没有 api_key 时失败
            if not resolved.api_url:
                resolved.api_url = base_resolved.api_url
            if not resolved.api_key:
                resolved.api_key = base_resolved.api_key
            if not resolved.model:
                resolved.model = base_resolved.model

            if repo_issue_config is not None and not resolved.inherit_global:
                config_source = "repo_config"
            elif global_issue_config is not None:
                config_source = "global_default"
            else:
                config_source = "env_default"

            effective_focus = list(
                focus_areas
                if focus_areas
                else (resolved.default_focus or base_resolved.default_focus)
            )

            issue_session = await db_service.create_issue_session(
                repository_id=repository_id,
                issue_number=issue_number,
                trigger_type=trigger_type,
                engine=resolved.engine,
                model=resolved.model,
                config_source=config_source,
                issue_title=issue_title,
                issue_author=issue_author,
                issue_state=issue_state,
                source_comment_id=source_comment_id,
            )
            issue_session_id = issue_session.id

        return (
            repository_id,
            actor_user_id,
            issue_session_id,
            resolved,
            config_source,
            effective_focus,
        )

    async def _find_similar_issue_candidates(
        self,
        owner: str,
        repo_name: str,
        issue_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        issues = await self.gitea_client.list_issues(
            owner,
            repo_name,
            state="all",
            limit=SIMILAR_ISSUE_FETCH_LIMIT,
        )
        if not issues:
            return []

        current_number = issue_data.get("number")
        scored: List[tuple[int, Dict[str, Any]]] = []
        for item in issues:
            if item.get("number") == current_number:
                continue
            score, reason = self._score_issue_similarity(issue_data, item)
            if score <= 0:
                continue
            candidate = {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "url": item.get("html_url") or item.get("url") or "",
                "body_excerpt": (item.get("body") or "")[:600],
                "label_names": [
                    label.get("name")
                    for label in item.get("labels", [])
                    if isinstance(label, dict) and label.get("name")
                ],
                "score_reason": reason,
            }
            scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], item[1].get("number") or 0))
        return [candidate for _, candidate in scored[:SIMILAR_ISSUE_LIMIT]]

    def _score_issue_similarity(
        self,
        current_issue: Dict[str, Any],
        candidate_issue: Dict[str, Any],
    ) -> tuple[int, str]:
        current_words = self._extract_keywords(
            f"{current_issue.get('title', '')} {current_issue.get('body', '')}"
        )
        candidate_words = self._extract_keywords(
            f"{candidate_issue.get('title', '')} {candidate_issue.get('body', '')}"
        )
        current_labels = {
            label.get("name", "").lower()
            for label in current_issue.get("labels", [])
            if isinstance(label, dict) and label.get("name")
        }
        candidate_labels = {
            label.get("name", "").lower()
            for label in candidate_issue.get("labels", [])
            if isinstance(label, dict) and label.get("name")
        }

        overlap_words = current_words & candidate_words
        overlap_labels = current_labels & candidate_labels
        title_overlap = self._extract_keywords(current_issue.get("title", "")) & self._extract_keywords(
            candidate_issue.get("title", "")
        )

        score = len(overlap_words) + len(title_overlap) * 2 + len(overlap_labels) * 3
        reason_parts = []
        if title_overlap:
            reason_parts.append(f"标题重合词 {', '.join(sorted(title_overlap)[:3])}")
        if overlap_words:
            reason_parts.append(f"描述关键词重合 {', '.join(sorted(overlap_words)[:3])}")
        if overlap_labels:
            reason_parts.append(f"标签重合 {', '.join(sorted(overlap_labels)[:3])}")
        return score, "；".join(reason_parts) or "关键词重合"

    def _extract_keywords(self, text: str) -> set[str]:
        if not text:
            return set()
        lowered = text.lower()

        english_tokens = re.findall(r"[a-z0-9_/\-]{3,}", lowered)
        chinese_tokens: List[str] = []

        if _JIEBA_AVAILABLE:
            chinese_tokens = [
                token.strip()
                for token in jieba.lcut_for_search(lowered)  # type: ignore[union-attr]
                if token and len(token.strip()) >= 2
            ]
        else:  # fallback：直接按 2-gram 切分连续中文块
            for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
                chinese_tokens.extend(
                    chunk[i : i + 2] for i in range(len(chunk) - 1)
                )

        tokens = english_tokens + chinese_tokens
        counts = Counter(tokens)
        return {
            token
            for token, count in counts.items()
            if count >= 1 and token not in _STOP_WORDS and len(token) >= 2
        }

    def _build_placeholder_comment(self, trigger_type: str) -> str:
        source_text = "自动触发" if trigger_type == "auto" else "手动触发"
        return (
            f"## Issue 分析中\n\n当前为 `{source_text}`。\n\n"
            "正在读取仓库上下文并整理可执行解决方案，请稍候。"
        )

    def _build_failure_comment(self, error_message: str) -> str:
        return f"## Issue 分析失败\n\n{error_message.strip() or '未知错误'}"

    def _build_result_comment(
        self, payload: Dict[str, Any], *, fallback_mode: str = "tool"
    ) -> str:
        header = "## Issue 分析结果"
        if fallback_mode == "text_json":
            header += "\n\n> _注：本次结果来自文本 JSON 降级解析，部分字段可能不完整。_"
        elif fallback_mode == "raw_text":
            header += "\n\n> _注：本次结果为原始文本降级输出，未产生结构化结果。_"

        parts = [header, "", payload.get("summary_markdown", "").strip() or "未生成摘要"]

        related_issues = payload.get("related_issues") or []
        if related_issues:
            parts.extend(["", "### 相似 Issue 参考"])
            for item in related_issues:
                parts.append(
                    "- #{number} {title} ({state})\n  - 原因: {reason}\n  - 参考点: {reference}\n  - 链接: {url}".format(
                        number=item.get("number", "?"),
                        title=item.get("title", "无标题"),
                        state=item.get("state", "unknown"),
                        reason=item.get("similarity_reason", "无"),
                        reference=item.get("suggested_reference", "无"),
                        url=item.get("url", ""),
                    )
                )

        solutions = payload.get("solution_suggestions") or []
        if solutions:
            parts.extend(["", "### 解决方案建议"])
            for index, item in enumerate(solutions, start=1):
                parts.append(f"{index}. **{item.get('title', '方案')}**")
                parts.append(f"   - 摘要: {item.get('summary', '无')}")
                steps = item.get("steps") or []
                for step in steps:
                    parts.append(f"   - 步骤: {step}")

        related_files = payload.get("related_files") or []
        if related_files:
            parts.extend(["", "### 相关文件"])
            for path in related_files:
                parts.append(f"- `{path}`")

        next_actions = payload.get("next_actions") or []
        if next_actions:
            parts.extend(["", "### 推荐下一步"])
            for action in next_actions:
                parts.append(f"- {action}")

        return "\n".join(parts).strip()

    async def _apply_issue_labels(
        self,
        owner: str,
        repo_name: str,
        issue_number: int,
        analysis_payload: Dict[str, Any],
    ) -> int:
        """成功时自动打 label；失败作为非致命日志，返回 Gitea 调用次数。"""
        labels_to_add: List[str] = [AI_ANALYZED_LABEL]
        if analysis_payload.get("related_issues"):
            labels_to_add.append(POSSIBLE_DUPLICATE_LABEL)

        calls = 0
        try:
            for label_name in labels_to_add:
                color = (
                    AI_ANALYZED_LABEL_COLOR
                    if label_name == AI_ANALYZED_LABEL
                    else POSSIBLE_DUPLICATE_LABEL_COLOR
                )
                ensured = await self.gitea_client.ensure_label_exists(
                    owner,
                    repo_name,
                    label_name,
                    color=color,
                    description=f"由 Issue 分析自动添加：{label_name}",
                )
                calls += 1
                if not ensured:
                    logger.debug("跳过无法确认的 label: %s", label_name)

            ok = await self.gitea_client.add_issue_labels(
                owner, repo_name, issue_number, labels_to_add
            )
            calls += 1
            if not ok:
                logger.info(
                    "Issue %s/%s#%s 自动 label 设置失败（非致命）",
                    owner,
                    repo_name,
                    issue_number,
                )
        except Exception as exc:  # pragma: no cover - 防御性保护
            logger.warning("自动打 label 失败: %s", exc)
        return calls
