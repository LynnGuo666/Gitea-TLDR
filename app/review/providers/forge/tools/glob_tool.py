"""Forge glob 工具"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Dict

from . import ForgeTool, iter_repo_files, resolve_repo_path

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def _matches_pattern(relative_path: Path, pattern: str) -> bool:
    normalized = relative_path.as_posix()
    candidate_patterns = {pattern}
    if pattern.startswith("**/"):
        candidate_patterns.add(pattern[3:])
    return any(fnmatch.fnmatch(normalized, item) for item in candidate_patterns)


class GlobTool(ForgeTool):
    @property
    def name(self) -> str:
        return "glob_files"

    @property
    def description(self) -> str:
        return "按 glob 模式快速查找仓库内文件，适合先缩小候选文件集合，再配合 search_code 或 read_file 精读。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "glob 模式，如 '**/*.py'、'frontend/**/*.tsx'",
                },
                "path": {
                    "type": "string",
                    "description": "可选的基准目录，相对于仓库根目录",
                },
                "limit": {
                    "type": "integer",
                    "description": f"最多返回多少个文件，默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        pattern = arguments.get("pattern", "")
        base_path = arguments.get("path", "")
        limit = arguments.get("limit", DEFAULT_LIMIT)

        if not isinstance(pattern, str) or not pattern.strip():
            return "错误: glob pattern 不能为空"
        if base_path is not None and not isinstance(base_path, str):
            return "错误: path 必须是字符串"
        if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            return f"错误: limit 必须是 1 到 {MAX_LIMIT} 之间的整数"

        try:
            repo_root, base_dir = resolve_repo_path(repo_path, base_path or ".")
        except ValueError as e:
            return f"错误: {e}"
        if not base_dir.exists():
            return f"错误: 路径不存在: {base_path or '.'}"
        if not base_dir.is_dir():
            return f"错误: 路径不是目录: {base_path or '.'}"

        matches: list[str] = []
        base_dir = base_dir.resolve()

        for _, relative in iter_repo_files(repo_root, base_path=base_dir):
            try:
                base_relative = (repo_root / relative).resolve().relative_to(base_dir)
            except ValueError:
                continue
            if _matches_pattern(base_relative, pattern):
                matches.append(str(relative))

        matches.sort()
        truncated = len(matches) > limit
        shown = matches[:limit]

        lines = [
            f"glob 模式: {pattern}",
            f"基准目录: {base_path or '/'}",
            f"匹配文件数: {len(matches)}",
            f"已截断: {'是' if truncated else '否'}",
        ]
        if shown:
            lines.append("结果:")
            lines.extend(f"- {match}" for match in shown)
        else:
            lines.append("结果: 无匹配文件")
        return "\n".join(lines)
