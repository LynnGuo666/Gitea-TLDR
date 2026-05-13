"""Issue 分析场景。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from ..api_client import AnthropicClient
from ..engine import ForgeEngine
from ..system_prompts import (
    build_issue_initial_message,
    build_issue_system_prompt,
)
from ..tools import get_tool_executor, get_tools_for_scenario
from ..types import ForgeResult, Scenario
from ...parsing import extract_json_payload


IssueFallbackMode = Literal["tool", "text_json", "raw_text"]


def _normalize_issue_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """清洗文本降级得到的 payload，确保关键字段都是安全类型。"""
    related_issues: List[Dict[str, Any]] = []
    for item in raw.get("related_issues", []) or []:
        if not isinstance(item, dict):
            continue
        related_issues.append(
            {
                "number": int(item.get("number", 0) or 0),
                "title": str(item.get("title", "") or ""),
                "state": str(item.get("state", "") or ""),
                "url": str(item.get("url", "") or ""),
                "similarity_reason": str(item.get("similarity_reason", "") or ""),
                "suggested_reference": str(item.get("suggested_reference", "") or ""),
            }
        )

    solution_suggestions: List[Dict[str, Any]] = []
    for item in raw.get("solution_suggestions", []) or []:
        if not isinstance(item, dict):
            continue
        steps = item.get("steps")
        if not isinstance(steps, list):
            steps = []
        solution_suggestions.append(
            {
                "title": str(item.get("title", "") or ""),
                "summary": str(item.get("summary", "") or ""),
                "steps": [str(step) for step in steps if str(step).strip()],
            }
        )

    return {
        "summary_markdown": str(raw.get("summary_markdown", "") or ""),
        "overall_severity": raw.get("overall_severity"),
        "related_issues": related_issues,
        "solution_suggestions": solution_suggestions,
        "related_files": [
            str(path) for path in raw.get("related_files", []) or [] if str(path).strip()
        ],
        "next_actions": [
            str(action) for action in raw.get("next_actions", []) or [] if str(action).strip()
        ],
    }


def finalize_issue_payload(
    result: ForgeResult,
) -> tuple[Dict[str, Any], IssueFallbackMode]:
    """把 ForgeResult 折叠成前端消费的 analysis payload，并告知降级路径。"""

    if result.structured_data:
        return _normalize_issue_payload(result.structured_data), "tool"

    parsed = extract_json_payload(result.final_text or "")
    if parsed:
        return _normalize_issue_payload(parsed), "text_json"

    fallback_text = (result.final_text or "").strip() or (result.error or "").strip()
    return (
        {
            "summary_markdown": fallback_text or "Issue 分析未返回结构化结果",
            "overall_severity": None,
            "related_issues": [],
            "solution_suggestions": [],
            "related_files": [],
            "next_actions": [],
        },
        "raw_text",
    )


async def run_issue(
    client: AnthropicClient,
    model: str,
    repo_path: Path,
    issue_info: Dict[str, Any],
    similar_issue_candidates: List[Dict[str, Any]],
    *,
    custom_prompt: Optional[str] = None,
    focus_areas: Optional[List[str]] = None,
    max_turns: int = 5,
    temperature: Optional[float] = None,
) -> ForgeResult:
    scenario = Scenario.ISSUE
    if max_turns < 1:
        raise ValueError("Forge max_turns 必须大于 0")

    system_prompt = build_issue_system_prompt(
        issue_info=issue_info,
        similar_issue_candidates=similar_issue_candidates,
        custom_prompt=custom_prompt,
        focus_areas=focus_areas,
    )
    initial_message = build_issue_initial_message(
        issue_info=issue_info,
        similar_issue_candidates=similar_issue_candidates,
    )
    tools = get_tools_for_scenario(scenario)
    tool_executor = get_tool_executor()
    engine = ForgeEngine(client=client, model=model, max_turns=max_turns)
    return await engine.run(
        system_prompt=system_prompt,
        initial_message=initial_message,
        tools=tools,
        tool_executor=tool_executor,
        repo_path=repo_path,
        scenario=scenario,
        temperature=temperature,
    )
