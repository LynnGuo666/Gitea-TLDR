"""
OpenAI Codex CLI Provider 实现

通过 `codex exec` 非交互模式调用 Codex CLI 进行代码审查。
每次调用动态生成隔离的 ``CODEX_HOME`` 目录与 ``config.toml``，
避免与用户全局配置冲突，并确保 provider / wire_api / model 等参数
完全受控。

文档：
- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/config-advanced
"""

import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import InlineComment, ReviewProvider, ReviewResult
from .parsing import (
    extract_json_payload as _shared_extract_json,
    parse_inline_comment as _shared_parse_inline,
    coerce_int as _shared_coerce_int,
    extract_actionable_error as _shared_extract_error,
)

logger = logging.getLogger(__name__)

# codex exec --output-schema 所用的 JSON Schema
# 与 ClaudeCodeProvider 要求的输出格式一致
_REVIEW_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary_markdown": {"type": "string"},
        "overall_severity": {
            "type": "string",
            "enum": ["critical", "high", "medium", "low", "info"],
        },
        "inline_comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "new_line": {"type": ["integer", "null"]},
                    "old_line": {"type": ["integer", "null"]},
                    "severity": {"type": ["string", "null"]},
                    "comment": {"type": "string"},
                    "suggestion": {"type": ["string", "null"]},
                },
                "required": ["path", "comment"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary_markdown", "overall_severity", "inline_comments"],
    "additionalProperties": False,
}

_PROVIDER_SECTION_NAME = "gitea_review"
_DEFAULT_WIRE_API = "responses"


class CodexProvider(ReviewProvider):
    """基于 OpenAI Codex CLI 的审查 Provider

    使用 ``codex exec`` 非交互模式分析 PR diff。
    默认运行于 read-only sandbox 以确保安全。

    每次调用会生成临时 ``CODEX_HOME`` 目录，写入 ``config.toml``
    以指定 model / provider / wire_api 等参数，从而与用户全局
    配置完全隔离。
    """

    PROVIDER_NAME = "codex_cli"
    DISPLAY_NAME = "Codex CLI"

    # diff 内容嵌入 prompt 时的最大字符数（防止超长 prompt）
    MAX_DIFF_CHARS = 200_000

    def __init__(self, cli_path: str = "codex", debug: bool = False):
        """初始化实例状态。

        Args:
            cli_path: CLI 可执行文件路径。
            debug: 是否启用调试模式。

        Returns:
            无返回值。
        """
        self.cli_path = cli_path
        self.debug = debug

    @property
    def name(self) -> str:
        """处理name相关逻辑。

        Args:
            无。

        Returns:
            字符串结果。
        """
        return self.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        """处理display name相关逻辑。

        Args:
            无。

        Returns:
            字符串结果。
        """
        return self.DISPLAY_NAME

    def _build_review_prompt(
        self,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """处理审查prompt相关逻辑。

        Args:
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            custom_prompt: 自定义提示词。

        Returns:
            字符串结果。
        """
        focus_map = {
            "quality": "代码质量和最佳实践",
            "security": "安全漏洞（SQL注入、XSS、命令注入等）",
            "performance": "性能问题和优化建议",
            "logic": "逻辑错误和潜在bug",
        }

        focus_text = "、".join([focus_map.get(f, f) for f in focus_areas])

        truncated = diff_content[: self.MAX_DIFF_CHARS]
        if len(diff_content) > self.MAX_DIFF_CHARS:
            truncated += "\n\n... (diff 内容过长，已截断)"

        prompt = f"""请审查以下Pull Request的代码变更。

**PR信息：**
- 标题: {pr_info.get("title", "N/A")}
- 描述: {pr_info.get("body", "N/A")}
- 作者: {pr_info.get("user", {}).get("login", "N/A")}

**审查重点：**
{focus_text}

**Diff内容：**
```diff
{truncated}
```

请完成以下审查任务：
1. **总体评价**：描述本次变更的整体风险、积极影响
2. **发现的问题**：按严重程度列出（严重/中等/轻微），解释原因
3. **改进建议**：给出可执行的修改建议
4. **优点**：指出值得保留或学习的实现

输出要求（必须严格遵守）：
- 最终输出为单个JSON对象，不要包含额外文本、注释或代码块标记
- `summary_markdown` 字段使用Markdown编写上述内容，结构清晰
- `overall_severity` 取值：critical/high/medium/low/info
- `inline_comments` 最多5条，逐条包含精确的 `path`、`new_line` (新增行号) 或 `old_line` (删除行号)、`comment`，可选 `suggestion` 与 `severity`
- `suggestion` 字段如果包含代码，必须使用 Markdown 代码块格式（```语言...```）
- 对无法定位的建议，省略该条，确保所有行号与diff一致

JSON结构示例：
{{
  "summary_markdown": "### 总体评价\\n...",
  "overall_severity": "medium",
  "inline_comments": [
    {{
      "path": "app/main.py",
      "new_line": 123,
      "old_line": null,
      "severity": "high",
      "comment": "描述问题与影响",
      "suggestion": "建议修改为：\\n```python\\nresult = safe_function(user_input)\\n```"
    }}
  ]
}}
"""
        if custom_prompt and custom_prompt.strip():
            prompt += f"\n\n**额外审查要求：**\n{custom_prompt.strip()}"
        return prompt

    # ------------------------------------------------------------------
    # CODEX_HOME / config.toml 生成
    # ------------------------------------------------------------------

    def _build_codex_home(
        self,
        api_url: Optional[str],
        api_key: Optional[str],
        model: Optional[str] = None,
        wire_api: Optional[str] = None,
    ) -> str:
        """生成临时 ``CODEX_HOME`` 目录并写入 ``config.toml``。

        Returns:
            临时目录的绝对路径，调用方负责在 finally 中清理。
        """
        codex_home = tempfile.mkdtemp(
            prefix="codex_home_", dir=self._resolve_codex_home_parent()
        )
        resolved_model = model
        resolved_wire_api = wire_api or _DEFAULT_WIRE_API

        lines = [
            f'model = "{resolved_model}"',
            f'model_provider = "{_PROVIDER_SECTION_NAME}"',
            'approval_policy = "never"',
            "",
            f"[model_providers.{_PROVIDER_SECTION_NAME}]",
            f'name = "Gitea PR Review"',
        ]

        if api_url:
            lines.append(f'base_url = "{api_url}"')

        lines.append(f'wire_api = "{resolved_wire_api}"')
        lines.append('env_key = "CODEX_API_KEY"')

        config_content = "\n".join(lines) + "\n"
        config_path = Path(codex_home) / "config.toml"
        config_path.write_text(config_content, encoding="utf-8")

        if self.debug:
            logger.debug(
                f"[{self.PROVIDER_NAME}] Generated CODEX_HOME={codex_home}\n"
                f"{config_content}"
            )

        return codex_home

    @staticmethod
    def _resolve_codex_home_parent() -> str:
        """处理Codex home parent相关逻辑。

        Args:
            无。

        Returns:
            字符串结果。
        """
        configured_parent = os.environ.get("CODEX_HOME_PARENT")
        if configured_parent and configured_parent.strip():
            parent = Path(configured_parent).expanduser()
        elif os.environ.get("WORK_DIR"):
            work_dir = Path(os.environ["WORK_DIR"]).expanduser()
            if work_dir.is_absolute():
                parent = work_dir
            else:
                project_root = Path(__file__).resolve().parents[3]
                parent = project_root / work_dir
        else:
            parent = Path.home() / ".cache" / "gitea-pr-reviewer"
        parent = parent.resolve()
        parent.mkdir(parents=True, exist_ok=True)
        return str(parent)

    def _build_env(
        self,
        codex_home: str,
        api_key: Optional[str],
    ) -> dict:
        """构建最小化子进程环境变量。

        只传递 ``CODEX_HOME``、``CODEX_API_KEY``、``PATH``、``HOME``，
        避免宿主 env 中的 ``OPENAI_*`` 等变量干扰 Codex CLI 行为。
        """
        minimal_env: Dict[str, str] = {
            "CODEX_HOME": codex_home,
            "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
        }
        if api_key:
            minimal_env["CODEX_API_KEY"] = api_key
        elif os.environ.get("OPENAI_API_KEY"):
            minimal_env["CODEX_API_KEY"] = os.environ["OPENAI_API_KEY"]

        if self.debug:
            safe_keys = {
                k: ("***" if "KEY" in k or "TOKEN" in k else v)
                for k, v in minimal_env.items()
            }
            logger.debug(f"[{self.PROVIDER_NAME}] Subprocess env: {safe_keys}")

        return minimal_env

    # ------------------------------------------------------------------
    # 核心分析方法
    # ------------------------------------------------------------------

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: Optional[str] = None,
        wire_api: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """分析pr。

        Args:
            repo_path: 本地仓库路径。
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            api_url: API 地址。
            api_key: API 密钥。
            custom_prompt: 自定义提示词。
            model: 模型名称。
            wire_api: 底层 API 协议标识。

        Returns:
            可能为空的结果。
        """
        self._clear_last_error()
        codex_home: Optional[str] = None
        try:
            prompt = self._build_review_prompt(
                diff_content, focus_areas, pr_info, custom_prompt
            )

            logger.info(f"开始使用 {self.DISPLAY_NAME} 分析PR，仓库路径: {repo_path}")

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Prompt]\n{prompt}")
                logger.debug(f"[Diff Content Length] {len(diff_content)} characters")

            if not model:
                self._set_last_error(
                    "Codex CLI 未配置模型名，请在仓库设置或全局设置中指定模型"
                )
                return None

            codex_home = self._build_codex_home(
                api_url,
                api_key,
                model=model,
                wire_api=wire_api,
            )
            env = self._build_env(codex_home, api_key)

            return await self._run_codex_exec(
                prompt,
                env,
                cwd=str(repo_path),
                model_name=model,
            )

        except Exception as e:
            logger.error(f"{self.DISPLAY_NAME} 分析异常: {e}", exc_info=True)
            self._set_last_error(f"{self.DISPLAY_NAME} 分析异常: {e}")
            return None
        finally:
            self._cleanup_codex_home(codex_home)

    @staticmethod
    def _cleanup_codex_home(codex_home: Optional[str]) -> None:
        """处理Codex home相关逻辑。

        Args:
            codex_home: 临时 Codex 配置目录。

        Returns:
            无返回值。
        """
        if codex_home:
            try:
                shutil.rmtree(codex_home, ignore_errors=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Codex exec 子进程调用
    # ------------------------------------------------------------------

    async def _run_codex_exec(
        self,
        prompt: str,
        env: dict,
        cwd: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """调用 ``codex exec`` 并解析结果。

        命令格式::

            codex exec \\
                --sandbox read-only \\
                --skip-git-repo-check \\
                --color never \\
                [--cd REPO_PATH] \\
                [--output-schema SCHEMA_FILE] \\
                [--output-last-message OUTPUT_FILE] \\
                -

        使用 --output-last-message 获取最终消息，减少 stdout 中日志/噪声对解析的影响。
        """
        schema_file = None
        output_file = None
        try:
            # 写入 output schema 到临时文件
            schema_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="codex_review_schema_",
                delete=False,
            )
            json.dump(_REVIEW_OUTPUT_SCHEMA, schema_file)
            schema_file.close()

            output_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                prefix="codex_review_output_",
                delete=False,
            )
            output_file.close()

            cmd: List[str] = [
                self.cli_path,
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--color",
                "never",
                "--output-schema",
                schema_file.name,
                "--output-last-message",
                output_file.name,
            ]

            if cwd:
                cmd.extend(["--cd", cwd])

            cmd.append("-")

            if self.debug:
                # 不打印 prompt（可能很长），只打印命令结构
                safe_cmd = [c if c != prompt else "<PROMPT>" for c in cmd]
                logger.debug(f"[{self.PROVIDER_NAME} Command] {safe_cmd}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=prompt.encode("utf-8")),
                    timeout=300.0,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                self._set_last_error(
                    "Codex CLI 执行超时（300s），请检查网络或 API 配置"
                )
                return None

            if process.returncode != 0:
                stderr_text = stderr.decode(errors="ignore").strip()
                stdout_text = stdout.decode(errors="ignore").strip()
                actionable_error = self._extract_actionable_error(
                    stderr_text, stdout_text
                )
                logger.error(
                    f"{self.DISPLAY_NAME} 执行失败 (返回码: {process.returncode})"
                )
                logger.error(f"Stdout: {stdout_text}")
                logger.error(f"Stderr: {stderr_text}")
                self._set_last_error(
                    actionable_error
                    or f"{self.DISPLAY_NAME} 执行失败，返回码 {process.returncode}"
                )
                return None

            result = ""
            if output_file:
                try:
                    result = Path(output_file.name).read_text(encoding="utf-8")
                except OSError:
                    result = ""

            if not result:
                result = stdout.decode(errors="ignore")

            if self.debug:
                logger.debug(f"[{self.PROVIDER_NAME} Response]\n{result}")
                if stderr:
                    logger.debug(f"[{self.PROVIDER_NAME} Stderr]\n{stderr.decode()}")

            parsed_result = self._parse_output(result)
            if not parsed_result:
                logger.error(f"{self.DISPLAY_NAME} 返回结果为空")
                self._set_last_error(f"{self.DISPLAY_NAME} 返回结果为空")
                return None

            if model_name:
                parsed_result.usage_metadata["model"] = model_name

            logger.info(f"{self.DISPLAY_NAME} 分析完成")
            return parsed_result

        finally:
            # 清理临时文件
            if schema_file:
                try:
                    os.unlink(schema_file.name)
                except OSError:
                    pass
            if output_file:
                try:
                    os.unlink(output_file.name)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # 输出解析（与 ClaudeCodeProvider 保持一致）
    # ------------------------------------------------------------------

    def _parse_output(self, output: str) -> Optional[ReviewResult]:
        """处理output相关逻辑。

        Args:
            output: 工具输出文本。

        Returns:
            可能为空的结果。
        """
        sanitized = (output or "").strip()
        if not sanitized:
            return None

        data = self._extract_json_payload(sanitized)
        if not data:
            logger.warning("响应未按JSON格式返回，将使用原始文本作为总结")
            return ReviewResult(
                summary_markdown=sanitized,
                inline_comments=[],
                raw_output=sanitized,
                provider_name=self.PROVIDER_NAME,
            )

        summary = str(
            data.get("summary_markdown")
            or data.get("summary")
            or data.get("report")
            or sanitized
        ).strip()
        severity = data.get("overall_severity") or data.get("severity")
        if isinstance(severity, str):
            severity = severity.strip()

        inline_comments: List[InlineComment] = []
        for item in data.get("inline_comments") or []:
            parsed = self._parse_inline_comment(item)
            if parsed:
                inline_comments.append(parsed)

        return ReviewResult(
            summary_markdown=summary or sanitized,
            inline_comments=inline_comments,
            overall_severity=severity,
            raw_output=sanitized,
            provider_name=self.PROVIDER_NAME,
        )

    def _parse_inline_comment(self, item: Dict[str, Any]) -> Optional[InlineComment]:
        result = _shared_parse_inline(item)
        return result

    def _extract_json_payload(self, text: str) -> Optional[Dict[str, Any]]:
        return _shared_extract_json(text)

    @staticmethod
    def _extract_actionable_error(stderr_text: str, stdout_text: str) -> str:
        return _shared_extract_error(stderr_text, stdout_text)

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        return _shared_coerce_int(value)
