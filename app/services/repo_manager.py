"""
代码库管理模块
"""

import os
import shutil
import asyncio
import logging
import stat
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RepoManager:
    """代码库管理器"""

    def __init__(self, work_dir: str):
        """
        初始化代码库管理器

        Args:
            work_dir: 工作目录路径
        """
        self.work_dir = Path(work_dir).expanduser().resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, owner: str, repo: str, pr_number: int) -> Path:
        """
        获取仓库的本地路径

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            仓库本地路径
        """
        return self.work_dir / f"{owner}_{repo}_pr{pr_number}"

    async def clone_repository(
        self,
        clone_url: str,
        owner: str,
        repo: str,
        pr_number: int,
        branch: str,
        auth_token: Optional[str] = None,
    ) -> Optional[Path]:
        """
        克隆仓库到本地

        Args:
            clone_url: 克隆URL（不带认证）
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号
            branch: 要检出的分支
            auth_token: 可选的访问令牌（通过 GIT_ASKPASS 注入）

        Returns:
            仓库本地路径，失败返回None
        """
        repo_path = self.get_repo_path(owner, repo, pr_number)

        # 如果目录已存在，先删除
        if repo_path.exists():
            logger.info(f"删除已存在的仓库目录: {repo_path}")
            shutil.rmtree(repo_path)

        askpass_script: Optional[Path] = None
        try:
            # 克隆仓库
            logger.info(f"开始克隆仓库: {owner}/{repo} 分支: {branch}")
            env, askpass_script = self._build_git_env(auth_token)
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                "--branch",
                branch,
                clone_url,
                str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            _, stderr = await process.communicate()

            if process.returncode != 0:
                stderr_text = stderr.decode(errors="ignore")
                logger.error("克隆仓库失败: %s", self._classify_clone_error(stderr_text))
                return None

            logger.info(f"成功克隆仓库到: {repo_path}")
            return repo_path

        except Exception as e:
            logger.error(f"克隆仓库异常: {e}")
            return None
        finally:
            if askpass_script and askpass_script.exists():
                try:
                    askpass_script.unlink()
                except OSError:
                    pass

    async def checkout_pr_branch(
        self, repo_path: Path, base_branch: str, head_branch: str
    ) -> bool:
        """
        检出PR的head分支

        Args:
            repo_path: 仓库路径
            base_branch: 基础分支
            head_branch: PR的head分支

        Returns:
            是否成功
        """
        try:
            # 如果head_branch和base_branch不同，尝试检出
            if head_branch != base_branch:
                logger.info(f"检出分支: {head_branch}")
                process = await asyncio.create_subprocess_exec(
                    "git",
                    "checkout",
                    head_branch,
                    cwd=str(repo_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(f"检出分支失败: {stderr.decode()}")
                    return False

            return True

        except Exception as e:
            logger.error(f"检出分支异常: {e}")
            return False

    def cleanup_repository(self, owner: str, repo: str, pr_number: int) -> bool:
        """
        清理仓库目录

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pr_number: PR编号

        Returns:
            是否成功
        """
        repo_path = self.get_repo_path(owner, repo, pr_number)

        if not repo_path.exists():
            return True

        try:
            logger.info(f"清理仓库目录: {repo_path}")
            shutil.rmtree(repo_path)
            return True
        except Exception as e:
            logger.error(f"清理仓库目录失败: {e}")
            return False

    def cleanup_all(self) -> bool:
        """
        清理所有仓库目录

        Returns:
            是否成功
        """
        try:
            if self.work_dir.exists():
                logger.info(f"清理所有仓库目录: {self.work_dir}")
                shutil.rmtree(self.work_dir)
                self.work_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"清理所有仓库目录失败: {e}")
            return False

    def _build_git_env(self, auth_token: Optional[str]) -> tuple[dict[str, str], Optional[Path]]:
        """构造 git 子进程环境，避免把 token 写入命令参数。"""
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        if not auth_token:
            return env, None

        askpass_content = (
            "#!/bin/sh\n"
            'case "$1" in\n'
            '  *Username*) echo "oauth2" ;;\n'
            '  *Password*) echo "$GITEA_TOKEN" ;;\n'
            "  *) echo ;;\n"
            "esac\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="git_askpass_",
            dir=str(self.work_dir),
            delete=False,
            encoding="utf-8",
        ) as fp:
            fp.write(askpass_content)
            script_path = Path(fp.name)

        script_path.chmod(stat.S_IRWXU)
        env["GIT_ASKPASS"] = str(script_path)
        env["GITEA_TOKEN"] = auth_token
        return env, script_path

    @staticmethod
    def _classify_clone_error(stderr_text: str) -> str:
        normalized = stderr_text.lower()
        if "authentication failed" in normalized or "could not read username" in normalized:
            return "认证失败（请检查 Gitea Token 权限）"
        if "remote branch" in normalized and "not found" in normalized:
            return "目标分支不存在"
        if "could not resolve host" in normalized or "name or service not known" in normalized:
            return "网络或域名解析失败"
        if "repository not found" in normalized:
            return "仓库不存在或无访问权限"
        return "git clone 执行失败"
