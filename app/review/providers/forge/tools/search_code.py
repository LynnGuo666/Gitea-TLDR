"""Forge search_code 工具"""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path
from typing import Any, Dict

from . import ForgeTool, iter_repo_files, resolve_repo_path

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_LINE_LENGTH = 200
MAX_SNIPPET_LENGTH = 240


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _trim_snippet(text: str, limit: int = MAX_SNIPPET_LENGTH) -> str:
    compact = text.strip().replace("\n", "\\n")
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _matches_glob(relative: Path, glob_pattern: str) -> bool:
    normalized = relative.as_posix()
    candidate_patterns = {glob_pattern}
    if glob_pattern.startswith("**/"):
        candidate_patterns.add(glob_pattern[3:])
    return any(fnmatch.fnmatch(normalized, item) for item in candidate_patterns) or (
        fnmatch.fnmatch(relative.name, glob_pattern)
    )


class SearchCodeTool(ForgeTool):
    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return (
            "grep 风格的仓库搜索工具。支持正则表达式、目录范围、glob 过滤、"
            "大小写控制与多种输出模式，用于查找定义、引用或相似实现。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "搜索关键词或正则表达式"},
                "path": {
                    "type": "string",
                    "description": "可选搜索目录或单文件，相对于仓库根目录",
                },
                "glob": {
                    "type": "string",
                    "description": "文件过滤模式，如 '*.py'、'frontend/**/*.tsx'",
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["content", "files_with_matches", "count"],
                    "description": "输出内容、文件列表或计数；默认 content",
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "是否忽略大小写，默认 true",
                },
                "multiline": {
                    "type": "boolean",
                    "description": "是否启用跨行匹配，默认 false",
                },
                "line_numbers": {
                    "type": "boolean",
                    "description": "content 模式下是否显示行号，默认 true",
                },
                "file_type": {
                    "type": "string",
                    "description": "按扩展名过滤文件，如 py、ts、go",
                },
                "head_limit": {
                    "type": "integer",
                    "description": f"最多返回多少条结果，默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}",
                },
                "offset": {
                    "type": "integer",
                    "description": "结果偏移量，默认 0",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        pattern = arguments.get("pattern", "")
        search_path = arguments.get("path", "")
        glob_pattern = arguments.get("glob")
        output_mode = arguments.get("output_mode", "content")
        ignore_case = arguments.get("ignore_case", True)
        multiline = arguments.get("multiline", False)
        line_numbers = arguments.get("line_numbers", True)
        file_type = arguments.get("file_type")
        head_limit = arguments.get("head_limit", DEFAULT_LIMIT)
        offset = arguments.get("offset", 0)

        if not isinstance(pattern, str) or not pattern.strip():
            return "错误: 搜索模式不能为空"
        if search_path is not None and not isinstance(search_path, str):
            return "错误: path 必须是字符串"
        if glob_pattern is not None and not isinstance(glob_pattern, str):
            return "错误: glob 必须是字符串"
        if output_mode not in {"content", "files_with_matches", "count"}:
            return "错误: output_mode 必须是 content/files_with_matches/count"
        if not isinstance(ignore_case, bool):
            return "错误: ignore_case 必须是布尔值"
        if not isinstance(multiline, bool):
            return "错误: multiline 必须是布尔值"
        if not isinstance(line_numbers, bool):
            return "错误: line_numbers 必须是布尔值"
        if file_type is not None and not isinstance(file_type, str):
            return "错误: file_type 必须是字符串"
        if not isinstance(head_limit, int) or head_limit < 1 or head_limit > MAX_LIMIT:
            return f"错误: head_limit 必须是 1 到 {MAX_LIMIT} 之间的整数"
        if not isinstance(offset, int) or offset < 0:
            return "错误: offset 必须是大于等于 0 的整数"

        try:
            repo_root, target = resolve_repo_path(repo_path, search_path or ".")
        except ValueError as e:
            return f"错误: {e}"
        if not target.exists():
            return f"错误: 路径不存在: {search_path or '.'}"

        flags = re.MULTILINE
        if ignore_case:
            flags |= re.IGNORECASE
        if multiline:
            flags |= re.DOTALL
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"错误: 无效的正则表达式: {e}"

        files_to_search: list[tuple[Path, Path]] = []
        try:
            if target.is_file():
                relative = target.resolve().relative_to(repo_root)
                files_to_search = [(target.resolve(), relative)]
            else:
                files_to_search = list(iter_repo_files(repo_root, base_path=target))
        except ValueError as e:
            return f"错误: {e}"

        matched_files: list[str] = []
        content_lines: list[str] = []
        total_matches = 0

        for file_path, relative in files_to_search:
            if glob_pattern and not _matches_glob(relative, glob_pattern):
                continue
            if file_type and file_path.suffix.lower().lstrip(".") != file_type.lower():
                continue
            try:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                matches_in_file = list(regex.finditer(content))
                if not matches_in_file:
                    continue
                matched_files.append(str(relative))
                total_matches += len(matches_in_file)

                if output_mode == "count":
                    continue

                if output_mode == "files_with_matches":
                    continue

                if multiline:
                    for match in matches_in_file:
                        start_line = _line_number(content, match.start())
                        end_line = _line_number(content, match.end())
                        prefix = (
                            f"{relative}:{start_line}-{end_line}: "
                            if line_numbers
                            else f"{relative}: "
                        )
                        snippet = _trim_snippet(match.group(0))
                        content_lines.append(prefix + snippet)
                    continue

                lines = content.splitlines()
                for line_no, line in enumerate(lines, start=1):
                    if not regex.search(line):
                        continue
                    prefix = f"{relative}:{line_no}: " if line_numbers else f"{relative}: "
                    content_lines.append(prefix + line.strip()[:MAX_LINE_LENGTH])
            except Exception as e:
                logger.debug("search_code 跳过文件 %s: %s", file_path, e)

        if output_mode == "count":
            shown_files = matched_files[offset : offset + head_limit]
            truncated = len(matched_files) > offset + head_limit
            next_offset = offset + len(shown_files) if truncated else None
            lines = [
                f"搜索模式: {pattern}",
                "输出模式: count",
                f"匹配文件数: {len(matched_files)}",
                f"总匹配数: {total_matches}",
                f"偏移: {offset}",
                f"限制: {head_limit}",
                f"已截断: {'是' if truncated else '否'}",
                f"next_offset: {next_offset if next_offset is not None else 'null'}",
            ]
            if shown_files:
                lines.append("文件:")
                lines.extend(f"- {filename}" for filename in shown_files)
            return "\n".join(lines)

        if output_mode == "files_with_matches":
            shown_files = matched_files[offset : offset + head_limit]
            truncated = len(matched_files) > offset + head_limit
            next_offset = offset + len(shown_files) if truncated else None
            lines = [
                f"搜索模式: {pattern}",
                "输出模式: files_with_matches",
                f"匹配文件数: {len(matched_files)}",
                f"总匹配数: {total_matches}",
                f"偏移: {offset}",
                f"限制: {head_limit}",
                f"已截断: {'是' if truncated else '否'}",
                f"next_offset: {next_offset if next_offset is not None else 'null'}",
            ]
            if shown_files:
                lines.append("文件:")
                lines.extend(f"- {filename}" for filename in shown_files)
            else:
                lines.append("文件: 无匹配")
            return "\n".join(lines)

        shown_lines = content_lines[offset : offset + head_limit]
        truncated = len(content_lines) > offset + head_limit
        next_offset = offset + len(shown_lines) if truncated else None
        lines = [
            f"搜索模式: {pattern}",
            "输出模式: content",
            f"匹配文件数: {len(matched_files)}",
            f"总匹配数: {total_matches}",
            f"返回条目数: {len(content_lines)}",
            f"偏移: {offset}",
            f"限制: {head_limit}",
            f"已截断: {'是' if truncated else '否'}",
            f"next_offset: {next_offset if next_offset is not None else 'null'}",
        ]
        if shown_lines:
            lines.append("结果:")
            lines.extend(shown_lines)
        else:
            lines.append("结果: 无匹配内容")
        return "\n".join(lines)
