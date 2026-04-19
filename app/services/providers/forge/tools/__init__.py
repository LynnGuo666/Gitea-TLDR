"""Forge 工具基类与注册表"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Awaitable, Dict, Iterator, Iterable

from ..types import ForgeToolResult, ForgeToolCall, Scenario, ToolDefinition

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}


class ForgeTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]: ...

    def to_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    def to_api_format(self) -> Dict[str, Any]:
        return self.to_definition().to_api_format()

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str: ...


def resolve_repo_path(repo_path: Path, raw_path: str = "") -> tuple[Path, Path]:
    """将用户输入路径解析到仓库内，并拒绝任何越界访问。"""
    repo_root = repo_path.resolve()
    target = (repo_root / (raw_path or ".")).resolve()

    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"路径超出仓库范围: {raw_path}") from exc

    return repo_root, target


def to_repo_relative(repo_root: Path, target: Path) -> Path:
    """将目标路径转换为仓库相对路径；越界时抛错。"""
    resolved = target.resolve()
    try:
        return resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"路径超出仓库范围: {target}") from exc


def iter_repo_files(
    repo_path: Path,
    *,
    base_path: Path | None = None,
    ignored_dirs: Iterable[str] = IGNORED_DIRS,
) -> Iterator[tuple[Path, Path]]:
    """安全遍历仓库文件，返回 (绝对路径, 仓库相对路径)。"""
    repo_root = repo_path.resolve()
    walk_root = (base_path or repo_root).resolve()

    try:
        walk_root.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"遍历路径超出仓库范围: {walk_root}") from exc

    ignored = set(ignored_dirs)
    for dirpath, dirnames, filenames in os.walk(walk_root, followlinks=False):
        current_dir = Path(dirpath)
        try:
            current_relative = current_dir.relative_to(repo_root)
        except ValueError:
            continue

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in ignored
            and not dirname.startswith(".")
            and (current_dir / dirname).resolve().is_relative_to(repo_root)
        ]

        if any(part in ignored or part.startswith(".") for part in current_relative.parts):
            continue

        for filename in filenames:
            if filename.startswith("."):
                continue
            file_path = current_dir / filename
            try:
                resolved = file_path.resolve()
                relative = resolved.relative_to(repo_root)
            except ValueError:
                continue
            if any(part in ignored or part.startswith(".") for part in relative.parts):
                continue
            if resolved.is_file():
                yield resolved, relative


from .read_file import ReadFileTool
from .search_code import SearchCodeTool
from .glob_tool import GlobTool
from .list_directory import ListDirectoryTool
from .lsp_tool import LSPTool
from .submit_analysis import SubmitAnalysisTool
from .submit_review import SubmitReviewTool

_READ_FILE = ReadFileTool()
_SEARCH_CODE = SearchCodeTool()
_GLOB = GlobTool()
_LIST_DIRECTORY = ListDirectoryTool()
_LSP = LSPTool()
_SUBMIT_ANALYSIS = SubmitAnalysisTool()
_SUBMIT_REVIEW = SubmitReviewTool()

_TOOL_MAP = {
    _READ_FILE.name: _READ_FILE,
    _SEARCH_CODE.name: _SEARCH_CODE,
    _GLOB.name: _GLOB,
    _LIST_DIRECTORY.name: _LIST_DIRECTORY,
    _LSP.name: _LSP,
    _SUBMIT_ANALYSIS.name: _SUBMIT_ANALYSIS,
    _SUBMIT_REVIEW.name: _SUBMIT_REVIEW,
}


def get_tools_for_scenario(scenario: Scenario) -> list[ForgeTool]:
    base = [_LIST_DIRECTORY, _GLOB, _SEARCH_CODE, _READ_FILE, _LSP]
    if scenario == Scenario.REVIEW:
        return base + [_SUBMIT_REVIEW]
    if scenario == Scenario.ISSUE:
        return base + [_SUBMIT_ANALYSIS]
    raise ValueError(f"Forge 场景暂未实现: {scenario.value}")


def get_tool_executor():
    async def _executor(tool_call: ForgeToolCall, repo_path: Path) -> ForgeToolResult:
        tool = _TOOL_MAP.get(tool_call.name)
        if tool is None:
            return ForgeToolResult(
                tool_call_id=tool_call.id,
                content=f"未知工具: {tool_call.name}",
                is_error=True,
            )
        try:
            content = await tool.execute(tool_call.arguments, repo_path)
            return ForgeToolResult(
                tool_call_id=tool_call.id, content=content, is_error=False
            )
        except Exception as e:
            return ForgeToolResult(
                tool_call_id=tool_call.id, content=f"工具执行错误: {e}", is_error=True
            )

    return _executor
