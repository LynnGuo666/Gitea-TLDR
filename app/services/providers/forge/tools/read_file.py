"""Forge read_file 工具"""

import logging
from pathlib import Path
from typing import Any, Dict

from . import ForgeTool, resolve_repo_path

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
        if not isinstance(file_path, str) or not file_path.strip():
            return "错误: 文件路径不能为空"

        try:
            _, target = resolve_repo_path(repo_path, file_path)
        except ValueError as e:
            return f"错误: {e}"
        if not target.is_file():
            return f"错误: 文件不存在: {file_path}"
        if target.stat().st_size > MAX_FILE_SIZE:
            return f"错误: 文件过大 ({target.stat().st_size} 字节)，最大允许 {MAX_FILE_SIZE} 字节"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            all_lines = content.splitlines()
            if start_line or end_line:
                actual_start = max(1, int(start_line or 1))
                actual_end = min(int(end_line or len(all_lines)), len(all_lines))
                if actual_end < actual_start:
                    return "错误: 行号范围无效"
                lines = all_lines[actual_start - 1 : actual_end]
                header = f"文件: {file_path} (行 {actual_start}-{actual_end})"
            else:
                lines = all_lines
                header = f"文件: {file_path} ({len(lines)} 行)"
            return f"{header}\n```\n" + "\n".join(lines) + "\n```"
        except Exception as e:
            return f"错误: 读取文件失败: {e}"
