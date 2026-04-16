from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.providers.forge.tools.list_directory import ListDirectoryTool
from app.services.providers.forge.tools.read_file import ReadFileTool
from app.services.providers.forge.tools.search_code import SearchCodeTool


def test_read_file_reads_repo_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    file_path = repo / "src.py"
    file_path.write_text("line1\nline2\nline3\n", encoding="utf-8")

    result = asyncio.run(
        ReadFileTool().execute({"path": "src.py", "start_line": 2, "end_line": 3}, repo)
    )

    assert "文件: src.py (行 2-3)" in result
    assert "line2" in result
    assert "line3" in result
    assert "line1" not in result


def test_read_file_rejects_parent_escape_to_sibling_with_same_prefix(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sibling = tmp_path / "repo2"
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret", encoding="utf-8")

    result = asyncio.run(ReadFileTool().execute({"path": "../repo2/secret.txt"}, repo))

    assert "路径超出仓库范围" in result


def test_list_directory_rejects_parent_escape_to_sibling_with_same_prefix(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    sibling = tmp_path / "repo2"
    sibling.mkdir()

    result = asyncio.run(ListDirectoryTool().execute({"path": "../repo2"}, repo))

    assert "路径超出仓库范围" in result


def test_search_code_limits_matches_and_skips_ignored_directories(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("needle\nother\nneedle\n", encoding="utf-8")
    ignored = repo / "node_modules"
    ignored.mkdir()
    (ignored / "ignored.js").write_text("needle\n", encoding="utf-8")

    result = asyncio.run(SearchCodeTool().execute({"pattern": "needle"}, repo))

    assert "app.py:1: needle" in result
    assert "app.py:3: needle" in result
    assert "ignored.js" not in result
