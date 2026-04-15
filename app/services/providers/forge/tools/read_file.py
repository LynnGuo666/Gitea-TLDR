"""Forge read_file 工具"""

import logging
from pathlib import Path
from typing import Any, Dict

from . import ForgeTool

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 500_000


class ReadFileTool(ForgeTool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取仓库中指定文件的内容。审查时用于查看相关源文件、测试文件、配置文件等。可指定行号范围。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于仓库根目录的文件路径"},
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（1-based），可选",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（1-based），可选",
                },
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        file_path = arguments.get("path", "")
        start_line = arguments.get("start_line")
        end_line = arguments.get("end_line")
        target = (repo_path / file_path).resolve()

        if not str(target).startswith(str(repo_path.resolve())):
            return f"错误: 路径超出仓库范围: {file_path}"
        if not target.is_file():
            return f"错误: 文件不存在: {file_path}"
        if target.stat().st_size > MAX_FILE_SIZE:
            return f"错误: 文件过大 ({target.stat().st_size} 字节)，最大允许 {MAX_FILE_SIZE} 字节"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if start_line or end_line:
                s = max(1, (start_line or 1)) - 1
                e = end_line or len(lines)
                lines = lines[s:e]
                header = (
                    f"文件: {file_path} (行 {start_line or 1}-{end_line or len(lines)})"
                )
            else:
                header = f"文件: {file_path} ({len(lines)} 行)"
            return f"{header}\n```\n" + "\n".join(lines) + "\n```"
        except Exception as e:
            return f"错误: 读取文件失败: {e}"
