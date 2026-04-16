"""Forge read_file 工具"""

import logging
from pathlib import Path
from typing import Any, Dict

from . import ForgeTool, resolve_repo_path

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 500_000
DEFAULT_LIMIT = 200
MAX_LIMIT = 400


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
                "offset": {
                    "type": "integer",
                    "description": "从第几行开始读取（1-based），默认 1",
                },
                "limit": {
                    "type": "integer",
                    "description": f"最多读取多少行，默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}",
                },
                "start_line": {
                    "type": "integer",
                    "description": "兼容旧参数：起始行号（1-based）",
                },
                "end_line": {
                    "type": "integer",
                    "description": "兼容旧参数：结束行号（1-based）",
                },
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        file_path = arguments.get("path", "")
        offset = arguments.get("offset")
        limit = arguments.get("limit")
        start_line = arguments.get("start_line")
        end_line = arguments.get("end_line")
        if not isinstance(file_path, str) or not file_path.strip():
            return "错误: 文件路径不能为空"
        if offset is not None and (not isinstance(offset, int) or offset < 1):
            return "错误: offset 必须是大于等于 1 的整数"
        if limit is not None and (
            not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT
        ):
            return f"错误: limit 必须是 1 到 {MAX_LIMIT} 之间的整数"
        if start_line is not None and (not isinstance(start_line, int) or start_line < 1):
            return "错误: start_line 必须是大于等于 1 的整数"
        if end_line is not None and (not isinstance(end_line, int) or end_line < 1):
            return "错误: end_line 必须是大于等于 1 的整数"

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
            total_lines = len(all_lines)

            if total_lines == 0:
                actual_start = 0
                actual_end = 0
                lines: list[str] = []
            elif start_line is not None or end_line is not None:
                actual_start = max(1, int(start_line or 1))
                requested_end = int(end_line or total_lines)
                if requested_end < actual_start:
                    return "错误: 行号范围无效"
                if actual_start > total_lines:
                    actual_start = total_lines + 1
                    actual_end = total_lines
                    lines = []
                else:
                    actual_end = min(requested_end, total_lines)
                    lines = all_lines[actual_start - 1 : actual_end]
            else:
                actual_start = int(offset or 1)
                actual_limit = int(limit or DEFAULT_LIMIT)
                if actual_start > total_lines:
                    actual_end = total_lines
                    lines = []
                else:
                    actual_end = min(actual_start + actual_limit - 1, total_lines)
                    lines = all_lines[actual_start - 1 : actual_end]

            has_more = actual_end < total_lines
            next_offset = actual_end + 1 if has_more else None

            body = "\n".join(
                f"{index}\t{line}"
                for index, line in enumerate(lines, start=actual_start)
            )
            shown_start = actual_start if lines else 0
            shown_end = actual_end if lines else 0
            metadata = [
                f"文件: {file_path}",
                f"显示行: {shown_start}-{shown_end}",
                f"总行数: {total_lines}",
                f"has_more: {'true' if has_more else 'false'}",
                f"next_offset: {next_offset if next_offset is not None else 'null'}",
            ]
            return "\n".join(metadata) + "\n```\n" + body + "\n```"
        except Exception as e:
            return f"错误: 读取文件失败: {e}"
