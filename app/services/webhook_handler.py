"""
Webhook处理模块
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core import settings
from app.services.claude_analyzer import (
    ClaudeAnalyzer,
    ClaudeReviewResult,
    InlineCommentSuggestion,
)
from app.services.command_parser import CommandParser
from app.services.gitea_client import GiteaClient
from app.services.repo_manager import RepoManager

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Webhook处理器"""

    def __init__(
        self,
        gitea_client: GiteaClient,
        repo_manager: RepoManager,
        claude_analyzer: ClaudeAnalyzer,
        bot_username: Optional[str] = None,
    ):
        """
        初始化Webhook处理器

        Args:
            gitea_client: Gitea客户端
            repo_manager: 仓库管理器
            claude_analyzer: Claude分析器
            bot_username: Bot用户名
        """
        self.gitea_client = gitea_client
        self.repo_manager = repo_manager
        self.claude_analyzer = claude_analyzer
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
        self, payload: Dict[str, Any], features: List[str], focus_areas: List[str]
    ) -> bool:
        """
        处理Pull Request事件

        Args:
            payload: Webhook payload
            features: 启用的功能列表
            focus_areas: 审查重点列表

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
            )

        except Exception as e:
            logger.error(f"处理PR异常: {e}", exc_info=True)
            return False

    async def process_webhook_async(
        self, payload: Dict[str, Any], features: List[str], focus_areas: List[str]
    ):
        """
        异步处理webhook（后台任务）

        Args:
            payload: Webhook payload
            features: 启用的功能列表
            focus_areas: 审查重点列表
        """
        try:
            await self.handle_pull_request(payload, features, focus_areas)
        except Exception as e:
            logger.error(f"异步处理webhook异常: {e}", exc_info=True)

    async def handle_issue_comment(
        self, payload: Dict[str, Any]
    ) -> bool:
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
            pr_data = await self.gitea_client.get_pull_request(owner, repo_name, pr_number)
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
                focus_areas=command.focus_areas
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
        features: List[str],
        focus_areas: List[str]
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

        Returns:
            是否处理成功
        """
        try:
            pr_title = pr_data.get("title")
            head_branch = pr_data.get("head", {}).get("ref")
            base_branch = pr_data.get("base", {}).get("ref")
            head_sha = pr_data.get("head", {}).get("sha")

            logger.info(
                f"执行PR审查: {owner}/{repo_name}#{pr_number} - {pr_title} "
                f"({head_branch} -> {base_branch})"
            )

            # 创建初始评论（如果启用了comment功能）
            comment_id = None
            if "comment" in features:
                initial_comment = "## 自动代码审查\n\n正在审查中，请稍候..."
                comment_id = await self.gitea_client.create_issue_comment(
                    owner, repo_name, pr_number, initial_comment
                )
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

            # 获取PR diff
            diff_content = await self.gitea_client.get_pull_request_diff(
                owner, repo_name, pr_number
            )

            if not diff_content:
                logger.error("无法获取PR diff")
                # 更新评论为错误状态
                if comment_id:
                    error_comment = "## 自动代码审查\n\n审查失败：无法获取PR diff"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                if "status" in features:
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description="无法获取PR diff",
                    )
                return False

            # 克隆仓库
            clone_url = self.gitea_client.get_clone_url(owner, repo_name)
            repo_path = await self.repo_manager.clone_repository(
                clone_url, owner, repo_name, pr_number, head_branch
            )

            if not repo_path:
                logger.error("无法克隆仓库")
                # 降级到简单模式
                logger.info("降级到简单模式（仅分析diff）")
                analysis_result = await self.claude_analyzer.analyze_pr_simple(
                    diff_content, focus_areas, pr_data
                )
            else:
                # 使用完整代码库分析
                analysis_result = await self.claude_analyzer.analyze_pr(
                    repo_path, diff_content, focus_areas, pr_data
                )

                # 清理仓库
                self.repo_manager.cleanup_repository(owner, repo_name, pr_number)

            if analysis_result is None:
                logger.error("Claude分析失败")
                # 更新评论为错误状态
                if comment_id:
                    error_comment = "## 自动代码审查\n\n审查失败：Claude分析过程出错"
                    await self.gitea_client.update_issue_comment(
                        owner, repo_name, comment_id, error_comment
                    )
                if "status" in features:
                    await self.gitea_client.create_commit_status(
                        owner,
                        repo_name,
                        head_sha,
                        "error",
                        description="代码审查失败",
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
                    success &= (new_comment_id is not None)

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
                success &= review_success

                # 如果review创建成功且配置了bot_username且启用了auto_request_reviewer，则自动请求审查者
                if review_success and settings.auto_request_reviewer and settings.bot_username:
                    await self.gitea_client.request_reviewer(
                        owner,
                        repo_name,
                        pr_number,
                        [settings.bot_username]
                    )

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

            logger.info(f"PR审查完成: {owner}/{repo_name}#{pr_number}")
            return success

        except Exception as e:
            logger.error(f"执行审查异常: {e}", exc_info=True)
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
        self, analysis_result: ClaudeReviewResult
    ) -> List[Dict[str, Any]]:
        """将Claude的行级建议转换成Gitea评论"""
        comments: List[Dict[str, Any]] = []
        for inline in analysis_result.inline_comments:
            payload = self._inline_to_review_comment(inline)
            if payload:
                comments.append(payload)
        return comments

    def _inline_to_review_comment(
        self, inline: InlineCommentSuggestion
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
