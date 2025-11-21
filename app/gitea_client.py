"""
Gitea API客户端模块
"""
import httpx
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class GiteaClient:
    """Gitea API客户端"""

    def __init__(self, base_url: str, token: str):
        """
        初始化Gitea客户端

        Args:
            base_url: Gitea服务器URL
            token: 访问令牌
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
        }

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取PR详情

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            PR详情字典
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取PR失败: {e}")
            return None

    async def get_pull_request_diff(
        self, owner: str, repo: str, pr_number: int
    ) -> Optional[str]:
        """
        获取PR的diff内容

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            diff文本内容
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}.diff"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"获取PR diff失败: {e}")
            return None

    async def get_pull_request_files(
        self, owner: str, repo: str, pr_number: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取PR修改的文件列表

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            文件列表
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}/files"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取PR文件列表失败: {e}")
            return None

    async def create_issue_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> Optional[int]:
        """
        在PR中创建评论

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号
            body: 评论内容

        Returns:
            评论ID，失败返回None
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/issues/{pr_number}/comments"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=self.headers, json={"body": body}
                )
                response.raise_for_status()
                comment_data = response.json()
                comment_id = comment_data.get("id")
                logger.info(f"成功创建PR评论: {owner}/{repo}#{pr_number}, ID: {comment_id}")
                return comment_id
        except Exception as e:
            logger.error(f"创建PR评论失败: {e}")
            return None

    async def update_issue_comment(
        self, owner: str, repo: str, comment_id: int, body: str
    ) -> bool:
        """
        更新PR评论

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            comment_id: 评论ID
            body: 新的评论内容

        Returns:
            是否成功
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/issues/comments/{comment_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url, headers=self.headers, json={"body": body}
                )
                response.raise_for_status()
                logger.info(f"成功更新PR评论: {owner}/{repo}, 评论ID: {comment_id}")
                return True
        except Exception as e:
            logger.error(f"更新PR评论失败: {e}")
            return False

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        创建PR审查

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号
            body: 审查内容
            event: 审查事件类型 (APPROVE, REQUEST_CHANGES, COMMENT)
            comments: 行级评论列表

        Returns:
            是否成功
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"成功创建PR审查: {owner}/{repo}#{pr_number}")
                return True
        except Exception as e:
            logger.error(f"创建PR审查失败: {e}")
            return False

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
        """
        创建提交状态

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            sha: 提交SHA
            state: 状态 (pending, success, error, failure, warning)
            context: 状态上下文
            description: 状态描述
            target_url: 目标URL

        Returns:
            是否成功
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/statuses/{sha}"
        payload = {
            "state": state,
            "context": context,
            "description": description,
            "target_url": target_url,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"成功设置提交状态: {owner}/{repo}@{sha[:7]} -> {state}")
                return True
        except Exception as e:
            logger.error(f"设置提交状态失败: {e}")
            return False

    def get_clone_url(self, owner: str, repo: str) -> str:
        """
        获取仓库克隆URL（带认证）

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            克隆URL
        """
        # 从base_url提取主机名
        from urllib.parse import urlparse

        parsed = urlparse(self.base_url)
        host = parsed.netloc

        # 构建带token的克隆URL
        return f"https://{self.token}@{host}/{owner}/{repo}.git"
