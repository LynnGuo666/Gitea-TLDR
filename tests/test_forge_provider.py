from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.providers.base import InlineComment
from app.services.providers.forge.engine import ForgeEngine
from app.services.providers.forge.provider import ForgeProvider
from app.services.providers.forge.tools import get_tools_for_scenario
from app.services.providers.forge.types import ForgeResult, ForgeUsage, Scenario


def test_get_tools_for_review_scenario_includes_submit_review():
    tools = get_tools_for_scenario(Scenario.REVIEW)

    assert [tool.name for tool in tools] == [
        "list_directory",
        "glob_files",
        "search_code",
        "read_file",
        "lsp",
        "submit_review",
    ]


def test_get_tools_for_non_review_scenario_raises():
    with pytest.raises(ValueError, match="暂未实现"):
        get_tools_for_scenario(Scenario.ISSUE)


def test_forge_provider_convert_result_uses_structured_data():
    provider = ForgeProvider()
    result = ForgeResult(
        success=True,
        scenario=Scenario.REVIEW,
        structured_data={
            "summary_markdown": "发现 1 个问题",
            "overall_severity": "high",
            "inline_comments": [
                {
                    "path": "app/main.py",
                    "comment": "这里缺少边界校验",
                    "new_line": 12,
                    "severity": "high",
                    "suggestion": "补充判空分支",
                }
            ],
        },
        usage=ForgeUsage(input_tokens=10, output_tokens=5),
        turns=2,
        tool_calls=3,
    )

    review = provider._convert_result(result, "claude-test")

    assert review.summary_markdown == "发现 1 个问题"
    assert review.overall_severity == "high"
    assert review.inline_comments == [
        InlineComment(
            path="app/main.py",
            comment="这里缺少边界校验",
            new_line=12,
            old_line=None,
            severity="high",
            suggestion="补充判空分支",
        )
    ]
    assert review.usage_metadata["tool_calls"] == 3
    assert review.usage_metadata["turns"] == 2


def test_forge_provider_convert_result_falls_back_to_json_text():
    provider = ForgeProvider()
    result = ForgeResult(
        success=True,
        scenario=Scenario.REVIEW,
        final_text=(
            "结论如下：\n"
            '```json\n{"summary_markdown":"ok","overall_severity":"low","inline_comments":[]}\n```'
        ),
        usage=ForgeUsage(input_tokens=3, output_tokens=4),
        turns=1,
    )

    review = provider._convert_result(result, "claude-test")

    assert review.summary_markdown == "ok"
    assert review.overall_severity == "low"
    assert review.inline_comments == []


def test_forge_provider_convert_result_falls_back_to_plain_text():
    provider = ForgeProvider()
    result = ForgeResult(
        success=True,
        scenario=Scenario.REVIEW,
        final_text="纯文本结果",
        usage=ForgeUsage(input_tokens=1, output_tokens=2),
        turns=1,
    )

    review = provider._convert_result(result, "claude-test")

    assert review.summary_markdown == "纯文本结果"
    assert review.raw_output == "纯文本结果"
    assert review.inline_comments == []


def test_forge_provider_analyze_pr_passes_configured_max_turns(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = ForgeProvider()
    captured: dict[str, object] = {}

    async def fake_run_review(**kwargs):
        captured.update(kwargs)
        return ForgeResult(
            success=True,
            scenario=Scenario.REVIEW,
            structured_data={
                "summary_markdown": "ok",
                "overall_severity": "low",
                "inline_comments": [],
            },
        )

    monkeypatch.setattr("app.services.providers.forge.provider.run_review", fake_run_review)
    monkeypatch.setattr(
        "app.services.providers.forge.provider.settings.forge_api_key", "secret"
    )
    monkeypatch.setattr(
        "app.services.providers.forge.provider.settings.forge_base_url",
        "https://example.com",
    )
    monkeypatch.setattr(
        "app.services.providers.forge.provider.settings.forge_model", "claude-test"
    )
    monkeypatch.setattr(
        "app.services.providers.forge.provider.settings.forge_max_turns", 9
    )

    review = asyncio.run(
        provider.analyze_pr(
            repo_path=PROJECT_ROOT,
            diff_content="diff --git a/a b/a",
            focus_areas=["quality"],
            pr_info={},
        )
    )

    assert review is not None
    assert captured["max_turns"] == 9
    assert captured["model"] == "claude-test"


def test_forge_provider_prefers_explicit_api_over_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = ForgeProvider()
    created: dict[str, object] = {}

    class DummyClient:
        def __init__(self, api_key: str, base_url: str):
            created["api_key"] = api_key
            created["base_url"] = base_url

    async def fake_run_review(**kwargs):
        created["client"] = kwargs["client"]
        return ForgeResult(
            success=True,
            scenario=Scenario.REVIEW,
            structured_data={
                "summary_markdown": "ok",
                "overall_severity": "low",
                "inline_comments": [],
            },
        )

    monkeypatch.setattr("app.services.providers.forge.provider.AnthropicClient", DummyClient)
    monkeypatch.setattr("app.services.providers.forge.provider.run_review", fake_run_review)
    monkeypatch.setattr(
        "app.services.providers.forge.provider.settings.forge_api_key", "settings-key"
    )
    monkeypatch.setattr(
        "app.services.providers.forge.provider.settings.forge_base_url",
        "https://settings.example.com",
    )

    review = asyncio.run(
        provider.analyze_pr(
            repo_path=PROJECT_ROOT,
            diff_content="diff --git a/a b/a",
            focus_areas=["quality"],
            pr_info={},
            api_url="https://override.example.com",
            api_key="override-key",
        )
    )

    assert review is not None
    assert created["api_key"] == "override-key"
    assert created["base_url"] == "https://override.example.com"


def test_forge_engine_serializes_forge_tool_instances_for_api():
    captured: dict[str, object] = {}

    class FakeClient:
        async def create_message(self, **kwargs):
            captured.update(kwargs)
            return {"content": [], "stop_reason": "end_turn"}, ForgeUsage()

        @staticmethod
        def parse_text_content(content_blocks):
            return ""

        @staticmethod
        def parse_tool_calls(content_blocks):
            return []

    async def fake_tool_executor(tool_call, repo_path):
        raise AssertionError("本测试不应执行到工具调用")

    engine = ForgeEngine(client=FakeClient(), model="claude-test", max_turns=1)
    result = asyncio.run(
        engine.run(
            system_prompt="test",
            initial_message="hello",
            tools=get_tools_for_scenario(Scenario.REVIEW),
            tool_executor=fake_tool_executor,
            repo_path=PROJECT_ROOT,
            scenario=Scenario.REVIEW,
        )
    )

    assert result.success is True
    serialized_tools = captured["tools"]
    assert isinstance(serialized_tools, list)
    assert serialized_tools[0]["name"] == "list_directory"
    assert serialized_tools[-1]["name"] == "submit_review"
