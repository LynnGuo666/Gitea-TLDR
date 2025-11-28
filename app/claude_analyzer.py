"""
Claude Code CLI调用模块
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class ClaudeAnalyzer:
    """Claude Code分析器"""

    def __init__(self, claude_code_path: str = "claude", debug: bool = False):
        """
        初始化Claude分析器

        Args:
            claude_code_path: Claude Code CLI的路径
            debug: 是否开启debug模式
        """
        self.claude_code_path = claude_code_path
        self.debug = debug

    def _build_review_prompt(
        self, diff_content: str, focus_areas: List[str], pr_info: dict
    ) -> str:
        """
        构建审查提示词

        Args:
            diff_content: PR的diff内容
            focus_areas: 审查重点领域
            pr_info: PR信息

        Returns:
            审查提示词
        """
        focus_map = {
            "quality": "代码质量和最佳实践",
            "security": "安全漏洞（SQL注入、XSS、命令注入等）",
            "performance": "性能问题和优化建议",
            "logic": "逻辑错误和潜在bug",
        }

        focus_text = "、".join([focus_map.get(f, f) for f in focus_areas])

        prompt = f"""请审查以下Pull Request的代码变更。

**PR信息：**
- 标题: {pr_info.get('title', 'N/A')}
- 描述: {pr_info.get('body', 'N/A')}
- 作者: {pr_info.get('user', {}).get('login', 'N/A')}

**审查重点：**
{focus_text}

**代码变更（diff）：**
```diff
{diff_content}
```

请提供详细的代码审查报告，包括：
1. **总体评价**：对这次PR的整体评价
2. **发现的问题**：按严重程度列出（严重、中等、轻微）
3. **改进建议**：具体的代码改进建议
4. **优点**：值得肯定的地方

请使用Markdown格式输出，确保报告清晰易读。
"""
        return prompt

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
    ) -> Optional[str]:
        """
        使用Claude Code分析PR

        Args:
            repo_path: 仓库本地路径
            diff_content: PR的diff内容
            focus_areas: 审查重点领域
            pr_info: PR信息

        Returns:
            分析结果，失败返回None
        """
        try:
            # 构建审查提示词
            prompt = self._build_review_prompt(diff_content, focus_areas, pr_info)

            # 将提示词写入临时文件
            prompt_file = repo_path / ".pr_review_prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")

            logger.info(f"开始使用Claude Code分析PR，仓库路径: {repo_path}")

            # Debug日志：输出提示词
            if self.debug:
                logger.debug(f"[Claude Prompt]\n{prompt}")

            # 调用Claude Code CLI
            # 使用 --message 参数传递提示词
            process = await asyncio.create_subprocess_exec(
                self.claude_code_path,
                "--message",
                prompt,
                "--cwd",
                str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # 清理临时文件
            if prompt_file.exists():
                prompt_file.unlink()

            if process.returncode != 0:
                logger.error(f"Claude Code执行失败: {stderr.decode()}")
                return None

            result = stdout.decode()

            # Debug日志：输出Claude返回结果
            if self.debug:
                logger.debug(f"[Claude Response]\n{result}")
                if stderr:
                    logger.debug(f"[Claude Stderr]\n{stderr.decode()}")

            logger.info("Claude Code分析完成")
            return result

        except Exception as e:
            logger.error(f"Claude Code分析异常: {e}")
            return None

    async def analyze_pr_simple(
        self, diff_content: str, focus_areas: List[str], pr_info: dict
    ) -> Optional[str]:
        """
        简单模式：不依赖完整代码库，仅分析diff

        Args:
            diff_content: PR的diff内容
            focus_areas: 审查重点领域
            pr_info: PR信息

        Returns:
            分析结果，失败返回None
        """
        try:
            prompt = self._build_review_prompt(diff_content, focus_areas, pr_info)

            logger.info("开始使用Claude Code分析PR（简单模式）")

            # Debug日志：输出提示词
            if self.debug:
                logger.debug(f"[Claude Prompt - Simple Mode]\n{prompt}")

            # 调用Claude Code CLI
            process = await asyncio.create_subprocess_exec(
                self.claude_code_path,
                "--message",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Claude Code执行失败: {stderr.decode()}")
                return None

            result = stdout.decode()

            # Debug日志：输出Claude返回结果
            if self.debug:
                logger.debug(f"[Claude Response - Simple Mode]\n{result}")
                if stderr:
                    logger.debug(f"[Claude Stderr - Simple Mode]\n{stderr.decode()}")

            logger.info("Claude Code分析完成（简单模式）")
            return result

        except Exception as e:
            logger.error(f"Claude Code分析异常: {e}")
            return None
