"""Forge 最小可用 LSP 查询工具"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from . import ForgeTool, iter_repo_files, resolve_repo_path

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
}

SYMBOL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("class", re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_]\w*)", re.MULTILINE)),
    (
        "function",
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)", re.MULTILINE),
    ),
    (
        "function",
        re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(",
            re.MULTILINE,
        ),
    ),
    ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("enum", re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("function", re.compile(r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_]\w*)", re.MULTILINE)),
    ("type", re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+(?:struct|interface)", re.MULTILINE)),
    ("function", re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("struct", re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("enum", re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_]\w*)", re.MULTILINE)),
    ("trait", re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_]\w*)", re.MULTILINE)),
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


class LSPTool(ForgeTool):
    @property
    def name(self) -> str:
        return "lsp"

    @property
    def description(self) -> str:
        return (
            "最小可用的只读 LSP 查询工具。当前支持 workspace/symbol 和 "
            "textDocument/documentSymbol 两种查询，用于按符号名快速定位定义。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "支持 workspace/symbol 或 textDocument/documentSymbol",
                },
                "params": {
                    "type": "object",
                    "description": "查询参数；workspace/symbol 需要 query，可选 path/limit；documentSymbol 需要 path",
                },
            },
            "required": ["method"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        method = arguments.get("method")
        params = arguments.get("params") or {}

        if not isinstance(method, str) or not method.strip():
            return "错误: method 不能为空"
        if not isinstance(params, dict):
            return "错误: params 必须是对象"

        if method == "workspace/symbol":
            return self._workspace_symbol(repo_path, params)
        if method == "textDocument/documentSymbol":
            return self._document_symbol(repo_path, params)
        return (
            "错误: 当前 lsp 工具仅支持 workspace/symbol 和 "
            "textDocument/documentSymbol"
        )

    def _workspace_symbol(self, repo_path: Path, params: Dict[str, Any]) -> str:
        query = params.get("query", "")
        path = params.get("path", "")
        limit = params.get("limit", DEFAULT_LIMIT)

        if not isinstance(query, str) or not query.strip():
            return "错误: workspace/symbol 需要非空 query"
        if path is not None and not isinstance(path, str):
            return "错误: path 必须是字符串"
        if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            return f"错误: limit 必须是 1 到 {MAX_LIMIT} 之间的整数"

        try:
            _, base_dir = resolve_repo_path(repo_path, path or ".")
        except ValueError as e:
            return f"错误: {e}"

        results = self._collect_symbols(repo_path, base_dir, query=query, limit=limit)
        lines = [
            f"lsp method: workspace/symbol",
            f"query: {query}",
            f"搜索目录: {path or '/'}",
            f"命中符号数: {len(results)}",
        ]
        if results:
            lines.append("结果:")
            lines.extend(
                f"- {item['name']} [{item['kind']}] {item['path']}:{item['line']}"
                for item in results
            )
        else:
            lines.append("结果: 无匹配符号")
        return "\n".join(lines)

    def _document_symbol(self, repo_path: Path, params: Dict[str, Any]) -> str:
        path = params.get("path", "")
        if not isinstance(path, str) or not path.strip():
            return "错误: textDocument/documentSymbol 需要 path"

        try:
            repo_root, target = resolve_repo_path(repo_path, path)
        except ValueError as e:
            return f"错误: {e}"
        if not target.exists():
            return f"错误: 文件不存在: {path}"
        if not target.is_file():
            return f"错误: 路径不是文件: {path}"

        symbols = self._extract_file_symbols(repo_root, target)
        lines = [
            "lsp method: textDocument/documentSymbol",
            f"文件: {path}",
            f"符号数: {len(symbols)}",
        ]
        if symbols:
            lines.append("结果:")
            lines.extend(
                f"- {item['name']} [{item['kind']}] {item['path']}:{item['line']}"
                for item in symbols
            )
        else:
            lines.append("结果: 未识别到符号")
        return "\n".join(lines)

    def _collect_symbols(
        self,
        repo_path: Path,
        base_dir: Path,
        *,
        query: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        query_lower = query.lower()

        if base_dir.is_file():
            for symbol in self._extract_file_symbols(repo_path.resolve(), base_dir.resolve()):
                if query_lower in str(symbol["name"]).lower():
                    matches.append(symbol)
                if len(matches) >= limit:
                    return matches
            return matches

        for abs_path, _ in iter_repo_files(repo_path, base_path=base_dir):
            for symbol in self._extract_file_symbols(repo_path.resolve(), abs_path):
                if query_lower in str(symbol["name"]).lower():
                    matches.append(symbol)
                if len(matches) >= limit:
                    return matches
        return matches

    def _extract_file_symbols(
        self,
        repo_root: Path,
        file_path: Path,
    ) -> List[Dict[str, Any]]:
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return []
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        relative = file_path.resolve().relative_to(repo_root.resolve())
        symbols: List[Dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for kind, pattern in SYMBOL_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(1)
                line = _line_number(text, match.start())
                marker = (name, line)
                if marker in seen:
                    continue
                seen.add(marker)
                symbols.append(
                    {
                        "name": name,
                        "kind": kind,
                        "path": str(relative),
                        "line": line,
                    }
                )
        symbols.sort(key=lambda item: (str(item["path"]), int(item["line"]), str(item["name"])))
        return symbols
