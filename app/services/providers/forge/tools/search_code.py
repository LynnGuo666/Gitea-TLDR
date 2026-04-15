"""Forge search_code 工具"""

import logging
import re
from pathlib import Path
from typing import Any, Dict

from . import ForgeTool

logger = logging.getLogger(__name__)

MAX_RESULTS = 50
MAX_LINE_LENGTH = 200
IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    ".tox",
    ".mypy_cache",
}


class SearchCodeTool(ForgeTool):
    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return "在仓库中搜索包含指定模式的文件和行。用于查找相关定义、引用、或类似实现模式。支持正则表达式。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "搜索关键词或正则表达式"},
                "glob": {
                    "type": "string",
                    "description": "文件过滤模式，如 '*.py' 或 'src/**'",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        pattern = arguments.get("pattern", "")
        glob_pattern = arguments.get("glob", "*")
        if not pattern:
            return "错误: 搜索模式不能为空"

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"错误: 无效的正则表达式: {e}"

        matches = []
        try:
            for file_path in repo_path.rglob(glob_pattern):
                if not file_path.is_file():
                    continue
                relative = file_path.relative_to(repo_path)
                if any(
                    part.startswith(".") or part in IGNORED_DIRS
                    for part in relative.parts
                ):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for i, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        truncated = line.strip()[:MAX_LINE_LENGTH]
                        matches.append(f"{relative}:{i}: {truncated}")
                        if len(matches) >= MAX_RESULTS:
                            break
                if len(matches) >= MAX_RESULTS:
                    break
        except Exception as e:
            return f"搜索错误: {e}"

        if not matches:
            return f"未找到匹配 '{pattern}' 的内容"
        return f"搜索 '{pattern}' (共 {len(matches)} 条结果):\n" + "\n".join(matches)
