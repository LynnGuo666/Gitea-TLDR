"""
Gitea API客户端模块
"""

import httpx
from typing import Optional, Dict, Any, List
import logging
import json

logger = logging.getLogger(__name__)


class GiteaClient:
    """Gitea API客户端"""

    def __init__(self, base_url: str, token: str, debug: bool = False):
        """
        初始化Gitea客户端

        Args:
            base_url: Gitea服务器URL
            token: 访问令牌
            debug: 是否开启debug模式
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.debug = debug
        self.headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
        }

    def _log_debug(self, method: str, url: str, **kwargs):
        """记录debug日志"""
        if self.debug:
            logger.debug(f"[API请求] {method} {url}")
            if "json" in kwargs:
                logger.debug(
                    f"[请求体] {json.dumps(kwargs['json'], ensure_ascii=False, indent=2)}"
                )

    def _log_response(self, response: httpx.Response):
        """记录响应debug日志"""
        if self.debug:
            logger.debug(f"[响应状态] {response.status_code}")
            logger.debug(f"[响应头] {dict(response.headers)}")
            try:
                # 尝试解析JSON响应
                response_data = response.json()
                logger.debug(
                    f"[响应体] {json.dumps(response_data, ensure_ascii=False, indent=2)}"
                )
            except:
                # 如果不是JSON，记录文本内容（限制长度）
                text = response.text
                if len(text) > 1000:
                    logger.debug(f"[响应体] {text[:1000]}... (truncated)")
                else:
                    logger.debug(f"[响应体] {text}")

    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "all", limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取仓库的PR列表

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            state: PR状态 (open/closed/all)
            limit: 返回的PR数量

        Returns:
            PR列表
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls"
        params = {"state": state, "limit": limit, "sort": "recentupdate"}

        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params)
                self._log_response(response)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取PR列表失败: {e}")
            return None

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
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
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
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
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
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
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
        payload = {"body": body}
        try:
            self._log_debug("POST", url, json=payload)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                self._log_response(response)
                response.raise_for_status()
                comment_data = response.json()
                comment_id = comment_data.get("id")
                logger.info(
                    f"成功创建PR评论: {owner}/{repo}#{pr_number}, ID: {comment_id}"
                )
                return comment_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning(
                    f"权限不足，无法创建PR评论: {owner}/{repo}#{pr_number} (HTTP {e.response.status_code})"
                )
            else:
                logger.error(f"创建PR评论失败: {e}")
            return None
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
        url = (
            f"{self.base_url}/api/v1/repos/{owner}/{repo}/issues/comments/{comment_id}"
        )
        payload = {"body": body}
        try:
            self._log_debug("PATCH", url, json=payload)
            async with httpx.AsyncClient() as client:
                response = await client.patch(url, headers=self.headers, json=payload)
                self._log_response(response)
                response.raise_for_status()
                logger.info(f"成功更新PR评论: {owner}/{repo}, 评论ID: {comment_id}")
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning(
                    f"权限不足，无法更新PR评论: {owner}/{repo}, 评论ID: {comment_id} (HTTP {e.response.status_code})"
                )
            else:
                logger.error(f"更新PR评论失败: {e}")
            return False
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
        commit_id: Optional[str] = None,
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
            commit_id: 对应的提交SHA（用于精准定位行级评论）

        Returns:
            是否成功
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments
        if commit_id:
            payload["commit_id"] = commit_id

        try:
            self._log_debug("POST", url, json=payload)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                self._log_response(response)
                response.raise_for_status()
                logger.info(f"成功创建PR审查: {owner}/{repo}#{pr_number}")
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning(
                    f"权限不足，无法创建PR审查: {owner}/{repo}#{pr_number} (HTTP {e.response.status_code})"
                )
            else:
                logger.error(f"创建PR审查失败: {e}")
            return False
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
            self._log_debug("POST", url, json=payload)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                self._log_response(response)
                response.raise_for_status()
                logger.info(f"成功设置提交状态: {owner}/{repo}@{sha[:7]} -> {state}")
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning(
                    f"权限不足，无法设置提交状态: {owner}/{repo}@{sha[:7]} (HTTP {e.response.status_code})"
                )
            else:
                logger.error(f"设置提交状态失败: {e}")
            return False
        except Exception as e:
            logger.error(f"设置提交状态失败: {e}")
            return False

    async def request_reviewer(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        reviewers: List[str],
    ) -> bool:
        """
        请求PR审查者

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号
            reviewers: 审查者用户名列表

        Returns:
            是否成功
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers"
        payload = {"reviewers": reviewers}

        try:
            self._log_debug("POST", url, json=payload)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                self._log_response(response)
                response.raise_for_status()
                logger.info(
                    f"成功请求审查者: {owner}/{repo}#{pr_number} <- {reviewers}"
                )
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning(
                    f"权限不足，无法请求审查者: {owner}/{repo}#{pr_number} (HTTP {e.response.status_code})"
                )
            else:
                logger.error(f"请求审查者失败: {e}")
            return False
        except Exception as e:
            logger.error(f"请求审查者失败: {e}")
            return False

    async def get_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        获取仓库详细信息（包含权限）

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            仓库信息字典，包含permissions字段
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}"
        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取仓库信息失败: {e}")
            return None

    async def check_repo_permissions(
        self, owner: str, repo: str
    ) -> Optional[Dict[str, bool]]:
        """
        检查当前用户对仓库的权限

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            权限字典 {"admin": bool, "push": bool, "pull": bool}，失败返回None
        """
        repo_info = await self.get_repository(owner, repo)
        if not repo_info:
            return None

        permissions = repo_info.get("permissions", {})
        return {
            "admin": permissions.get("admin", False),
            "push": permissions.get("push", False),
            "pull": permissions.get("pull", False),
        }

    async def is_organization(self, org: str) -> bool:
        """判断 owner 是否为组织"""
        url = f"{self.base_url}/api/v1/orgs/{org}"
        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
                if response.status_code == 404:
                    return False
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"获取组织信息失败: {e}")
            return False

    async def get_org_membership_role(self, org: str, username: str) -> Optional[str]:
        """获取用户在组织中的角色"""
        url = f"{self.base_url}/api/v1/orgs/{org}/memberships/{username}"
        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
                role = data.get("role")
                return role.lower() if isinstance(role, str) else None
        except Exception as e:
            logger.error(f"获取组织成员角色失败: {e}")
            return None

    async def get_commits(
        self, owner: str, repo: str, sha: Optional[str] = None, limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取仓库的提交列表

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            sha: 分支名或提交SHA（默认获取默认分支）
            limit: 返回的提交数量

        Returns:
            提交列表
        """
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/commits"
        params = {"limit": limit}
        if sha:
            params["sha"] = sha

        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params)
                self._log_response(response)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取提交列表失败: {e}")
            return None

    async def list_user_repos(self) -> Optional[List[Dict[str, Any]]]:
        """列出当前token可访问的仓库"""

        url = f"{self.base_url}/api/v1/user/repos"
        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取仓库列表失败: {e}")
            return None

    async def list_repo_hooks(
        self, owner: str, repo: str
    ) -> Optional[List[Dict[str, Any]]]:
        """列出仓库的webhooks"""

        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/hooks"
        try:
            self._log_debug("GET", url)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                self._log_response(response)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"获取仓库webhooks失败: {e}")
            return None

    async def create_repo_hook(
        self, owner: str, repo: str, hook: Dict[str, Any]
    ) -> Optional[int]:
        """创建仓库webhook，返回hook ID"""

        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/hooks"
        try:
            self._log_debug("POST", url, json=hook)
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=hook)
                self._log_response(response)
                response.raise_for_status()
                hook_data = response.json()
                return hook_data.get("id")
        except Exception as e:
            logger.error(f"创建仓库webhook失败: {e}")
            return None

    async def update_repo_hook(
        self, owner: str, repo: str, hook_id: int, hook: Dict[str, Any]
    ) -> bool:
        """更新已有仓库webhook"""

        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/hooks/{hook_id}"
        try:
            self._log_debug("PATCH", url, json=hook)
            async with httpx.AsyncClient() as client:
                response = await client.patch(url, headers=self.headers, json=hook)
                self._log_response(response)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"更新仓库webhook失败: {e}")
            return False

    async def add_collaborator(self, owner: str, repo: str, username: str) -> bool:
        """邀请指定用户协作仓库"""

        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/collaborators/{username}"
        try:
            self._log_debug("PUT", url)
            async with httpx.AsyncClient() as client:
                response = await client.put(url, headers=self.headers)
                self._log_response(response)
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                logger.warning(
                    f"权限不足，无法邀请协作者: {owner}/{repo} <- {username} (HTTP {e.response.status_code})"
                )
            else:
                logger.error(f"邀请协作者失败: {e}")
            return False
        except Exception as e:
            logger.error(f"邀请协作者失败: {e}")
            return False

    async def ensure_repo_webhook(
        self, owner: str, repo: str, hook_definition: Dict[str, Any]
    ) -> Optional[int]:
        """确保仓库存在符合配置的webhook，返回hook id"""

        existing_hooks = await self.list_repo_hooks(owner, repo) or []
        target_url = hook_definition.get("config", {}).get("url")
        for hook in existing_hooks:
            if hook.get("config", {}).get("url") == target_url:
                updated = await self.update_repo_hook(
                    owner, repo, hook.get("id"), hook_definition
                )
                return hook.get("id") if updated else None

        return await self.create_repo_hook(owner, repo, hook_definition)

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
