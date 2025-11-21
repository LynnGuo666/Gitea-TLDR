"""
Webhook处理模块
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from .gitea_client import GiteaClient
from .repo_manager import RepoManager
from .claude_analyzer import ClaudeAnalyzer
from .config import settings

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Webhook处理器"""

    def __init__(
        self,
        gitea_client: GiteaClient,
        repo_manager: RepoManager,
        claude_analyzer: ClaudeAnalyzer,
    ):
        """
        初始化Webhook处理器

        Args:
            gitea_client: Gitea客户端
            repo_manager: 仓库管理器
            claude_analyzer: Claude分析器
        """
        self.gitea_client = gitea_client
        self.repo_manager = repo_manager
        self.claude_analyzer = claude_analyzer

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
            head_sha = pr_data.get("head", {}).get("sha")

            logger.info(
                f"处理PR: {owner}/{repo_name}#{pr_number} - {pr_title} "
                f"({head_branch} -> {base_branch})"
            )

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

            if not analysis_result:
                logger.error("Claude分析失败")
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

            # 发布评论
            if "comment" in features:
                comment_body = f"## 🤖 自动代码审查报告\n\n{analysis_result}"
                success &= await self.gitea_client.create_issue_comment(
                    owner, repo_name, pr_number, comment_body
                )

            # 创建Review
            if "review" in features:
                success &= await self.gitea_client.create_review(
                    owner,
                    repo_name,
                    pr_number,
                    analysis_result,
                    event="COMMENT",
                )

            # 设置状态
            if "status" in features:
                # 简单判断：如果分析结果中包含"严重"，设置为failure，否则success
                state = (
                    "failure"
                    if "严重" in analysis_result or "critical" in analysis_result.lower()
                    else "success"
                )
                success &= await self.gitea_client.create_commit_status(
                    owner,
                    repo_name,
                    head_sha,
                    state,
                    description="代码审查完成",
                )

            logger.info(f"PR处理完成: {owner}/{repo_name}#{pr_number}")
            return success

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
