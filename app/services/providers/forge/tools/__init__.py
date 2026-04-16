"""Forge 工具基类与注册表"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Awaitable, Dict

from ..types import ForgeToolResult, ForgeToolCall, Scenario, ToolDefinition


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


from .read_file import ReadFileTool
from .search_code import SearchCodeTool
from .list_directory import ListDirectoryTool
from .submit_review import SubmitReviewTool

_READ_FILE = ReadFileTool()
_SEARCH_CODE = SearchCodeTool()
_LIST_DIRECTORY = ListDirectoryTool()
_SUBMIT_REVIEW = SubmitReviewTool()

_TOOL_MAP = {
    _READ_FILE.name: _READ_FILE,
    _SEARCH_CODE.name: _SEARCH_CODE,
    _LIST_DIRECTORY.name: _LIST_DIRECTORY,
    _SUBMIT_REVIEW.name: _SUBMIT_REVIEW,
}


def get_tools_for_scenario(scenario: Scenario) -> list[ForgeTool]:
    base = [_READ_FILE, _SEARCH_CODE, _LIST_DIRECTORY]
    if scenario == Scenario.REVIEW:
        return base + [_SUBMIT_REVIEW]
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
