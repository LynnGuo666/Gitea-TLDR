"""
Webhook处理模块
"""

import logging
from typing import Any, Dict, List, Optional

from app.core import settings
from app.core.database import Database
from app.services.providers.base import (
    InlineComment,
    ReviewResult,
)
from app.services.review_engine import ReviewEngine
from app.services.command_parser import CommandParser
from app.services.db_service import DBService
from app.services.gitea_client import GiteaClient
from app.services.repo_manager import RepoManager

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Webhook处理器"""

    def __init__(
        self,
        gitea_client: GiteaClient,
        repo_manager: RepoManager,
        review_engine: ReviewEngine,
        database: Optional[Database] = None,
        bot_username: Optional[str] = None,
    ):
        self.gitea_client = gitea_client
        self.repo_manager = repo_manager
        self.review_engine = review_engine
        self.database = database
        self.command_parser = CommandParser(bot_username)

    def parse_review_features(self, features_header: Optional[str]) -> List[str]:
        """
        解析审查功能标头

        Args:
            features_header: X-Review-Features标头值

        Returns:
            功能列表
        """
        if not features_header:
            return ["comment"]  # 默认只发评论

        features = [f.strip().lower() for f in features_header.split(",")]
        valid_features = ["comment", "review", "status"]
        return [f for f in features if f in valid_features]

    def parse_review_focus(self, focus_header: Optional[str]) -> List[str]:
        """
        解析审查重点标头

        Args:
            focus_header: X-Review-Focus标头值

        Returns:
            审查重点列表
        """
        if not focus_header:
            return settings.default_review_focus

        focus_areas = [f.strip().lower() for f in focus_header.split(",")]
        valid_areas = ["quality", "security", "performance", "logic"]
        return [f for f in focus_areas if f in valid_areas]

    async def handle_pull_request(
        self,
        payload: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
    ) -> bool:
        """
        处理Pull Request事件

        Args:
            payload: Webhook payload
            features: 启用的功能列表（None 表示按仓库配置回退）
            focus_areas: 审查重点列表（None 表示按仓库配置回退）

        Returns:
            是否处理成功
        """
        try:
            action = payload.get("action")
            pr_data = payload.get("pull_request", {})
            repo_data = payload.get("repository", {})

            # 只处理opened和synchronized事件
            if action not in ["opened", "synchronized"]:
                logger.info(f"忽略PR事件: {action}")
                return True

            # 提取关键信息
            owner = repo_data.get("owner", {}).get("login")
            repo_name = repo_data.get("name")
            pr_number = pr_data.get("number")
            pr_title = pr_data.get("title")
            head_branch = pr_data.get("head", {}).get("ref")
            base_branch = pr_data.get("base", {}).get("ref")

            logger.info(
                f"处理PR: {owner}/{repo_name}#{pr_number} - {pr_title} "
                f"({head_branch} -> {base_branch})"
            )

            return await self._perform_review(
                owner=owner,
                repo_name=repo_name,
                pr_number=pr_number,
                pr_data=pr_data,
                features=features,
                focus_areas=focus_areas,
                trigger_type="auto",
            )

        except Exception as e:
            logger.error(f"处理PR异常: {e}", exc_info=True)
            return False

    async def process_webhook_async(
        self,
        payload: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
    ):
        """
        异步处理webhook（后台任务）

        Args:
            payload: Webhook payload
            features: 启用的功能列表（None 表示按仓库配置回退）
            focus_areas: 审查重点列表（None 表示按仓库配置回退）
        """
        try:
            await self.handle_pull_request(payload, features, focus_areas)
        except Exception as e:
            logger.error(f"异步处理webhook异常: {e}", exc_info=True)

    async def handle_issue_comment(self, payload: Dict[str, Any]) -> bool:
        """
        处理Issue评论事件（用于手动触发审查）

        Args:
            payload: Webhook payload

        Returns:
            是否处理成功
        """
        try:
            action = payload.get("action")
            comment_data = payload.get("comment", {})
            issue_data = payload.get("issue", {})
            repo_data = payload.get("repository", {})

            # 只处理新创建的评论
            if action != "created":
                logger.info(f"忽略评论事件: {action}")
                return True

            # 获取评论内容
            comment_body = comment_data.get("body", "")

            # 解析命令
            command = self.command_parser.parse_comment(comment_body)
            if not command:
                logger.debug("评论中未包含有效的bot命令")
                return True

            logger.info(f"检测到手动触发命令: {command.command}")

            # 检查是否是PR
            pull_request = issue_data.get("pull_request")
            if not pull_request:
                logger.info("评论不在PR中，忽略")
                return True

            # 提取PR信息
            owner = repo_data.get("owner", {}).get("login")
            repo_name = repo_data.get("name")
            pr_number = issue_data.get("number")

            logger.info(
                f"手动触发PR审查: {owner}/{repo_name}#{pr_number} "
                f"features={command.features}, focus={command.focus_areas}"
            )

            # 获取完整的PR信息
            pr_data = await self.gitea_client.get_pull_request(
                owner, repo_name, pr_number
            )
            if not pr_data:
                logger.error("无法获取PR详情")
                return False

            # 执行审查
            return await self._perform_review(
                owner=owner,
                repo_name=repo_name,
                pr_number=pr_number,
                pr_data=pr_data,
                features=command.features,
                focus_areas=command.focus_areas,
                trigger_type="manual",
            )

        except Exception as e:
            logger.error(f"处理评论异常: {e}", exc_info=True)
            return False

    async def _perform_review(
        self,
        owner: str,
        repo_name: str,
        pr_number: int,
        pr_data: Dict[str, Any],
        features: Optional[List[str]],
        focus_areas: Optional[List[str]],
        trigger_type: str = "auto",
    ) -> bool:
        """
        执行PR审查（核心逻辑，被自动和手动触发共用）

        Args:
            owner: 仓库所有者
            repo_name: 仓库名称
            pr_number: PR编号
            pr_data: PR详细数据
            features: 启用的功能列表
            focus_areas: 审查重点列表
            trigger_type: 触发类型 (auto/manual)

        Returns:
            是否处理成功
        """
        review_session_id = None
        repository_id = None
        analysis_mode = None
        diff_size = 0
        gitea_api_calls = 0
        clone_operations = 0

        try:
            pr_title = pr_data.get("title")
            pr_author = pr_data.get("user", {}).get("login")
            head_branch = pr_data.get("head", {}).get("ref")
            base_branch = pr_data.get("base", {}).get("ref")
            head_sha = pr_data.get("head", {}).get("sha")

            logger.info(
                f"执行PR审查: {owner}/{repo_name}#{pr_number} - {pr_title} "
                f"({head_branch} -> {base_branch})"
            )

            # 查询仓库的 Anthropic 配置
            api_url = None
            api_key = None
            wire_api = None
            engine = self.review_engine.default_provider_name
            model = None
            config_source = "global_default"

            # 创建数据库记录
            if self.database:
                async with self.database.session() as session:
                    db_service = DBService(session)
                    repo = await db_service.get_or_create_repository(owner, repo_name)
                    repository_id = repo.id

                    # 查询仓库的 ModelConfig 获取 Provider 配置
                    model_config = await db_service.get_model_config(repository_id)
                    if model_config:
                        api_url = model_config.api_url
                        api_key = model_config.api_key
                        wire_api = model_config.wire_api
                        engine = model_config.engine or engine
                        model = model_config.model or model
                        if model_config.repository_id == repository_id:
                            config_source = "repo_config"
                        else:
                            config_source = "global_default"

                        if focus_areas is None:
                            focus_areas = model_config.get_focus()
                        if features is None:
                            features = model_config.get_features()

                        if api_url or api_key:
                            logger.info(
                                f"使用仓库 {owner}/{repo_name} 的自定义 Anthropic 配置"
                            )

                    if focus_areas is None:
                        focus_areas = settings.default_review_focus
                    if features is None:
                        features = ["comment"]

                    review_session = await db_service.create_review_session(
                        repository_id=repository_id,
                        pr_number=pr_number,
                        trigger_type=trigger_type,
                        engine=engine,
                        model=model,
                        config_source=config_source,
                        pr_title=pr_title,
                        pr_author=pr_author,
                        head_branch=head_branch,
                        base_branch=base_branch,
                        head_sha=head_sha,
                        enabled_features=features,
                        focus_areas=focus_areas,
                    )
                    review_session_id = review_session.id

            if focus_areas is None:
                focus_areas = settings.default_review_focus
            if features is None:
                features = ["comment"]

            # 创建初始评论（如果启用了comment功能）
            comment_id = None
            if "comment" in features:
                initial_comment = "## 自动代码审查\n\n正在审查中，请稍候..."
                comment_id = await self.gitea_client.create_issue_comment(
                    owner, repo_name, pr_number, initial_comment
                )
                gitea_api_calls += 1
                if comment_id:
                    logger.info(f"已创建初始评论，ID: {comment_id}")

            # 设置初始状态
            if "status" in features:
                await self.gitea_client.create_commit_status(
                    owner,
                    repo_name,
                    head_sha,
                    "pending",
                    description="代码审查进行中...",
                )
                gitea_api_calls += 1

            # 获取PR diff
            diff_content = await self.gitea_client.get_pull_request_diff(
                owner, repo_name, pr_number
            )
            gitea_api_calls += 1

            if not diff_content:
                logger.error("无法获取PR diff")
                # 更新评论为错误状态
                if comment_id:
                    error_comment = "## 自动代码审查\n\n审查失败：无法获取PR diff"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                    gitea_api_calls += 1
                if "status" in features:
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description="无法获取PR diff",
                    )
                    gitea_api_calls += 1

                # 更新数据库记录
                if self.database and review_session_id:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.update_review_session(
                            review_session_id,
                            overall_success=False,
                            error_message="无法获取PR diff",
                            completed=True,
                        )
                return False

            diff_size = len(diff_content)

            # 克隆仓库
            clone_url = self.gitea_client.get_clone_url(owner, repo_name)
            repo_path = await self.repo_manager.clone_repository(
                clone_url, owner, repo_name, pr_number, head_branch
            )
            clone_operations += 1

            if not repo_path:
                logger.error("无法克隆仓库")
                # 降级到简单模式
                logger.info("降级到简单模式（仅分析diff）")
                analysis_mode = "simple"
                analysis_result = await self.review_engine.analyze_pr_simple(
                    diff_content,
                    focus_areas,
                    pr_data,
                    api_url=api_url,
                    api_key=api_key,
                    engine=engine,
                    model=model,
                    wire_api=wire_api,
                )
            else:
                # 使用完整代码库分析
                analysis_mode = "full"
                analysis_result = await self.review_engine.analyze_pr(
                    repo_path,
                    diff_content,
                    focus_areas,
                    pr_data,
                    api_url=api_url,
                    api_key=api_key,
                    engine=engine,
                    model=model,
                    wire_api=wire_api,
                )

                # 清理仓库
                self.repo_manager.cleanup_repository(owner, repo_name, pr_number)

            if analysis_result is None:
                analysis_error = self.review_engine.last_error or "审查分析过程出错"
                logger.error(f"审查分析失败: {analysis_error}")
                # 更新评论为错误状态
                if comment_id:
                    error_comment = f"## 自动代码审查\n\n审查失败：{analysis_error}"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                    gitea_api_calls += 1
                if "status" in features:
                    status_desc = analysis_error.replace("\n", " ").strip()[:120]
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description=status_desc or "代码审查失败",
                    )
                    gitea_api_calls += 1

                # 更新数据库记录
                if self.database and review_session_id:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.update_review_session(
                            review_session_id,
                            engine=engine,
                            model=model,
                            config_source=config_source,
                            analysis_mode=analysis_mode,
                            diff_size_bytes=diff_size,
                            overall_success=False,
                            error_message=analysis_error,
                            completed=True,
                        )
                return False

            # 根据功能标头发布结果
            success = True

            summary_markdown = analysis_result.summary_text() or "未生成审查报告"

            # 更新或创建评论
            if "comment" in features:
                comment_body = f"## 自动代码审查报告\n\n{summary_markdown}"
                if comment_id:
                    # 更新已有评论
                    success &= await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, comment_body
                    )
                else:
                    # 如果初始评论创建失败，则创建新评论
                    new_comment_id = await self.gitea_client.create_issue_comment(
                        owner, repo_name, pr_number, comment_body
                    )
                    success &= new_comment_id is not None
                gitea_api_calls += 1

            # 创建Review
            if "review" in features:
                review_comments = self._build_review_comments(analysis_result)
                review_success = await self.gitea_client.create_review(
                    owner,
                    repo_name,
                    pr_number,
                    summary_markdown,
                    event="COMMENT",
                    comments=review_comments if review_comments else None,
                    commit_id=head_sha,
                )
                gitea_api_calls += 1
                success &= review_success

                # 如果review创建成功且配置了bot_username且启用了auto_request_reviewer，则自动请求审查者
                if (
                    review_success
                    and settings.auto_request_reviewer
                    and settings.bot_username
                ):
                    await self.gitea_client.request_reviewer(
                        owner, repo_name, pr_number, [settings.bot_username]
                    )
                    gitea_api_calls += 1

            # 设置状态
            if "status" in features:
                state = "failure" if analysis_result.indicates_failure() else "success"
                success &= await self.gitea_client.create_commit_status(
                    owner,
                    repo_name,
                    head_sha,
                    state,
                    description="代码审查完成",
                )
                gitea_api_calls += 1

            # 更新数据库记录
            if self.database and review_session_id:
                async with self.database.session() as session:
                    db_service = DBService(session)

                    # 更新审查会话
                    await db_service.update_review_session(
                        review_session_id,
                        engine=analysis_result.provider_name or engine,
                        model=(analysis_result.usage_metadata.get("model") or model),
                        config_source=config_source,
                        analysis_mode=analysis_mode,
                        diff_size_bytes=diff_size,
                        overall_severity=analysis_result.overall_severity,
                        summary_markdown=summary_markdown,
                        inline_comments_count=len(analysis_result.inline_comments),
                        overall_success=success,
                        completed=True,
                    )

                    # 保存行级评论
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
                        await db_service.save_inline_comments(
                            review_session_id, comments_data
                        )

                    # 记录使用量
                    if repository_id:
                        estimated_input = diff_size // 4 + 500  # 粗略估算
                        estimated_output = len(summary_markdown) // 4
                        await db_service.record_usage(
                            repository_id=repository_id,
                            review_session_id=review_session_id,
                            estimated_input_tokens=estimated_input,
                            estimated_output_tokens=estimated_output,
                            gitea_api_calls=gitea_api_calls,
                            provider_api_calls=1,
                            clone_operations=clone_operations,
                        )

            logger.info(f"PR审查完成: {owner}/{repo_name}#{pr_number}")
            return success

        except Exception as e:
            logger.error(f"执行审查异常: {e}", exc_info=True)

            # 更新数据库记录
            if self.database and review_session_id:
                try:
                    async with self.database.session() as session:
                        db_service = DBService(session)
                        await db_service.update_review_session(
                            review_session_id,
                            overall_success=False,
                            error_message=str(e),
                            completed=True,
                        )
                except Exception as db_error:
                    logger.error(f"更新数据库记录失败: {db_error}")

            return False

    async def process_comment_async(self, payload: Dict[str, Any]):
        """
        异步处理评论webhook（后台任务）

        Args:
            payload: Webhook payload
        """
        try:
            await self.handle_issue_comment(payload)
        except Exception as e:
            logger.error(f"异步处理评论异常: {e}", exc_info=True)

    def _build_review_comments(
        self, analysis_result: ReviewResult
    ) -> List[Dict[str, Any]]:
        """将行级建议转换成Gitea评论"""
        comments: List[Dict[str, Any]] = []
        for inline in analysis_result.inline_comments:
            payload = self._inline_to_review_comment(inline)
            if payload:
                comments.append(payload)
        return comments

    def _inline_to_review_comment(
        self, inline: InlineComment
    ) -> Optional[Dict[str, Any]]:
        """转换单条行级建议"""
        path = (inline.path or "").strip()
        if not path:
            return None

        body = inline.build_body()
        if not body:
            return None

        new_position = inline.new_line if inline.new_line is not None else 0
        old_position = inline.old_line if inline.old_line is not None else 0

        return {
            "path": path,
            "body": body,
            "new_position": new_position,
            "old_position": old_position,
        }
