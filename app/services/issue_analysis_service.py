"""
Issue 分析服务
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from app.core import settings
from app.core.database import Database
from app.services.db_service import DBService
from app.services.gitea_client import GiteaClient
from app.services.repo_manager import RepoManager
from app.services.providers.forge.api_client import AnthropicClient
from app.services.providers.forge.provider import (
    DEFAULT_FORGE_BASE_URL,
    DEFAULT_FORGE_MODEL,
)
from app.services.providers.forge.scenarios.issue import run_issue

logger = logging.getLogger(__name__)

SIMILAR_ISSUE_LIMIT = 5
SIMILAR_ISSUE_FETCH_LIMIT = 100
WORKSPACE_KIND = "issue"


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
            "执行 Issue 分析: %s/%s#%s - %s",
            owner,
            repo_name,
            issue_number,
            issue_title,
        )

        try:
            (
                repository_id,
                actor_user_id,
                issue_session_id,
                resolved_model,
                resolved_api_url,
                resolved_api_key,
                config_source,
                custom_prompt,
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

            if not resolved_api_key:
                raise RuntimeError("Forge: 未配置 API Key（FORGE_API_KEY 或仓库级 forge api_key）")

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
            client = AnthropicClient(
                api_key=resolved_api_key,
                base_url=resolved_api_url,
            )
            result = await run_issue(
                client=client,
                model=resolved_model,
                repo_path=repo_path,
                issue_info=issue_data,
                similar_issue_candidates=similar_issue_candidates,
                custom_prompt=custom_prompt,
                max_turns=max(1, int(getattr(settings, "forge_max_turns", 5) or 5)),
            )

            self.repo_manager.cleanup_workspace(
                owner, repo_name, WORKSPACE_KIND, issue_number
            )

            if not result.structured_data:
                error_text = result.error or "Issue 分析未返回结构化结果"
                raise RuntimeError(error_text)

            analysis_payload = self._normalize_analysis_payload(result.structured_data)
            comment_body = self._build_result_comment(analysis_payload)

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

            if self.database and issue_session_id and repository_id:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    await db_service.update_issue_session(
                        issue_session_id,
                        engine="forge",
                        model=result.model or resolved_model,
                        config_source=config_source,
                        issue_state=issue_state,
                        bot_comment_id=bot_comment_id,
                        overall_severity=analysis_payload.get("overall_severity"),
                        summary_markdown=analysis_payload.get("summary_markdown", ""),
                        analysis_payload=analysis_payload,
                        overall_success=success,
                        completed=True,
                    )
                    await db_service.record_usage(
                        repository_id=repository_id,
                        issue_session_id=issue_session_id,
                        user_id=actor_user_id,
                        estimated_input_tokens=result.usage.input_tokens,
                        estimated_output_tokens=result.usage.output_tokens,
                        cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
                        cache_read_input_tokens=result.usage.cache_read_input_tokens,
                        gitea_api_calls=gitea_api_calls,
                        provider_api_calls=1,
                        clone_operations=clone_operations,
                    )

            logger.info("Issue 分析完成: %s/%s#%s", owner, repo_name, issue_number)
            return success
        except Exception as e:
            logger.error("Issue 分析失败: %s", e, exc_info=True)
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
    ) -> tuple[int, Optional[int], Optional[int], str, str, str, str, Optional[str]]:
        repository_id = 0
        actor_user_id: Optional[int] = None
        issue_session_id: Optional[int] = None
        resolved_model = getattr(settings, "forge_model", DEFAULT_FORGE_MODEL)
        resolved_api_url = getattr(settings, "forge_base_url", DEFAULT_FORGE_BASE_URL)
        resolved_api_key = getattr(settings, "forge_api_key", "") or ""
        config_source = "global_default"
        custom_prompt: Optional[str] = None

        if not self.database:
            return (
                repository_id,
                actor_user_id,
                issue_session_id,
                resolved_model,
                resolved_api_url,
                resolved_api_key,
                config_source,
                custom_prompt,
            )

        async with self.database.session() as session:
            db_service = DBService(session)
            repo = await db_service.get_or_create_repository(owner, repo_name)
            repository_id = repo.id

            if actor_username:
                actor_user = await db_service.get_or_create_user_by_username(actor_username)
                actor_user_id = actor_user.id

            repo_config = await db_service.get_repo_specific_model_config(repository_id)
            if repo_config and (repo_config.engine or "").strip() == "forge":
                resolved_api_url = repo_config.api_url or resolved_api_url
                resolved_api_key = repo_config.api_key or resolved_api_key
                resolved_model = repo_config.model or resolved_model
                custom_prompt = repo_config.custom_prompt
                config_source = "repo_config"

            issue_session = await db_service.create_issue_session(
                repository_id=repository_id,
                issue_number=issue_number,
                trigger_type=trigger_type,
                engine="forge",
                model=resolved_model,
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
            resolved_model,
            resolved_api_url,
            resolved_api_key,
            config_source,
            custom_prompt,
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
        tokens = re.findall(r"[A-Za-z0-9_/\-]{3,}", text.lower())
        counts = Counter(tokens)
        return {token for token, count in counts.items() if count >= 1 and token not in {"issue", "error", "bug", "the", "and", "with", "that"}}

    def _build_placeholder_comment(self, trigger_type: str) -> str:
        source_text = "自动触发" if trigger_type == "auto" else "手动触发"
        return f"## Issue 分析中\n\n当前为 `{source_text}`。\n\n正在读取仓库上下文并整理可执行解决方案，请稍候。"

    def _build_failure_comment(self, error_message: str) -> str:
        return f"## Issue 分析失败\n\n{error_message.strip() or '未知错误'}"

    def _build_result_comment(self, payload: Dict[str, Any]) -> str:
        parts = ["## Issue 分析结果", "", payload.get("summary_markdown", "").strip() or "未生成摘要"]

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

    def _normalize_analysis_payload(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        related_issues = []
        for item in raw_payload.get("related_issues", []):
            if not isinstance(item, dict):
                continue
            related_issues.append(
                {
                    "number": int(item.get("number", 0) or 0),
                    "title": str(item.get("title", "") or ""),
                    "state": str(item.get("state", "") or ""),
                    "url": str(item.get("url", "") or ""),
                    "similarity_reason": str(item.get("similarity_reason", "") or ""),
                    "suggested_reference": str(item.get("suggested_reference", "") or ""),
                }
            )

        solution_suggestions = []
        for item in raw_payload.get("solution_suggestions", []):
            if not isinstance(item, dict):
                continue
            steps = item.get("steps")
            if not isinstance(steps, list):
                steps = []
            solution_suggestions.append(
                {
                    "title": str(item.get("title", "") or ""),
                    "summary": str(item.get("summary", "") or ""),
                    "steps": [str(step) for step in steps if str(step).strip()],
                }
            )

        return {
            "summary_markdown": str(raw_payload.get("summary_markdown", "") or ""),
            "overall_severity": raw_payload.get("overall_severity"),
            "related_issues": related_issues,
            "solution_suggestions": solution_suggestions,
            "related_files": [
                str(path) for path in raw_payload.get("related_files", []) if str(path).strip()
            ],
            "next_actions": [
                str(action) for action in raw_payload.get("next_actions", []) if str(action).strip()
            ],
        }
