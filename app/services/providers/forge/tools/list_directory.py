"""Forge list_directory 工具"""

from pathlib import Path
from typing import Any, Dict

from . import ForgeTool

MAX_ENTRIES = 100


class ListDirectoryTool(ForgeTool):
    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "列出仓库中指定目录的文件和子目录。用于了解项目结构、定位相关文件。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于仓库根目录的目录路径（默认为根目录）",
                },
            },
            "required": [],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path: Path) -> str:
        dir_path = arguments.get("path", "")
        target = (repo_path / dir_path).resolve()

        if not str(target).startswith(str(repo_path.resolve())):
            return f"错误: 路径超出仓库范围: {dir_path}"
        if not target.is_dir():
            return f"错误: 目录不存在: {dir_path}"

        entries = []
        for item in sorted(target.iterdir()):
            name = item.name
            if name.startswith("."):
                continue
            if item.is_dir():
                entries.append(f"[DIR]  {name}/")
            else:
                size = item.stat().st_size
                entries.append(f"[FILE] {name} ({size} bytes)")
            if len(entries) >= MAX_ENTRIES:
                entries.append(f"... (截断，共超过 {MAX_ENTRIES} 项)")
                break

        header = f"目录: {dir_path or '/'}"
        return header + "\n" + "\n".join(entries)
