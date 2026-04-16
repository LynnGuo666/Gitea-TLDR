from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.providers.forge.tools.glob_tool import GlobTool
from app.services.providers.forge.tools.list_directory import ListDirectoryTool
from app.services.providers.forge.tools.lsp_tool import LSPTool
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

    assert "文件: src.py" in result
    assert "显示行: 2-3" in result
    assert "2\tline2" in result
    assert "3\tline3" in result
    assert "1\tline1" not in result


def test_read_file_supports_offset_limit_pagination(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.py").write_text("a\nb\nc\nd\n", encoding="utf-8")

    result = asyncio.run(
        ReadFileTool().execute({"path": "src.py", "offset": 2, "limit": 2}, repo)
    )

    assert "显示行: 2-3" in result
    assert "has_more: true" in result
    assert "next_offset: 4" in result
    assert "2\tb" in result
    assert "3\tc" in result


def test_read_file_handles_empty_file_with_stable_pagination_metadata(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "empty.txt").write_text("", encoding="utf-8")

    result = asyncio.run(ReadFileTool().execute({"path": "empty.txt"}, repo))

    assert "显示行: 0-0" in result
    assert "总行数: 0" in result
    assert "has_more: false" in result
    assert "next_offset: null" in result


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


def test_glob_tool_matches_files_within_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    src = repo / "src"
    src.mkdir()
    (src / "a.py").write_text("print('a')\n", encoding="utf-8")
    (src / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")

    result = asyncio.run(
        GlobTool().execute({"pattern": "**/*.py", "path": "src"}, repo)
    )

    assert "匹配文件数: 1" in result
    assert "- src/a.py" in result
    assert "src/b.ts" not in result


def test_glob_tool_skips_ignored_directories(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "keep.py").write_text("print('ok')\n", encoding="utf-8")
    ignored = repo / "node_modules"
    ignored.mkdir()
    (ignored / "ignore.py").write_text("print('ignored')\n", encoding="utf-8")

    result = asyncio.run(GlobTool().execute({"pattern": "**/*.py"}, repo))

    assert "- keep.py" in result
    assert "ignore.py" not in result


def test_search_code_supports_files_with_matches_mode_and_skips_ignored_directories(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("needle\nother\nneedle\n", encoding="utf-8")
    ignored = repo / "node_modules"
    ignored.mkdir()
    (ignored / "ignored.js").write_text("needle\n", encoding="utf-8")

    result = asyncio.run(
        SearchCodeTool().execute(
            {"pattern": "needle", "output_mode": "files_with_matches"},
            repo,
        )
    )

    assert "输出模式: files_with_matches" in result
    assert "- app.py" in result
    assert "ignored.js" not in result


def test_search_code_blocks_symbolic_link_escape(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("needle\n", encoding="utf-8")
    (repo / "link.txt").symlink_to(outside)

    result = asyncio.run(
        SearchCodeTool().execute({"pattern": "needle", "output_mode": "content"}, repo)
    )

    assert "link.txt" not in result
    assert "无匹配内容" in result


def test_search_code_supports_content_mode_with_line_numbers(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("needle\nother\nneedle\n", encoding="utf-8")

    result = asyncio.run(
        SearchCodeTool().execute({"pattern": "needle", "output_mode": "content"}, repo)
    )

    assert "输出模式: content" in result
    assert "app.py:1: needle" in result
    assert "app.py:3: needle" in result


def test_search_code_supports_multiline_matches(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "result = call(\n    alpha,\n    beta,\n)\n",
        encoding="utf-8",
    )

    result = asyncio.run(
        SearchCodeTool().execute(
            {
                "pattern": r"call\(\s*alpha,\s*beta,\s*\)",
                "output_mode": "content",
                "multiline": True,
            },
            repo,
        )
    )

    assert "总匹配数: 1" in result
    assert "app.py:1-4: call(\\n    alpha,\\n    beta,\\n)" in result


def test_lsp_tool_supports_workspace_symbol_and_document_symbol(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "class ReviewEngine:\n    pass\n\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )

    workspace = asyncio.run(
        LSPTool().execute(
            {"method": "workspace/symbol", "params": {"query": "Review"}},
            repo,
        )
    )
    document = asyncio.run(
        LSPTool().execute(
            {"method": "textDocument/documentSymbol", "params": {"path": "main.py"}},
            repo,
        )
    )

    assert "ReviewEngine [class] main.py:1" in workspace
    assert "helper [function] main.py:" in document
