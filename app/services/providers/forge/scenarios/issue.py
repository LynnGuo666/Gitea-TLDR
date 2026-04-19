"""Issue 分析场景。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api_client import AnthropicClient
from ..engine import ForgeEngine
from ..system_prompts import (
    build_issue_initial_message,
    build_issue_system_prompt,
)
from ..tools import get_tool_executor, get_tools_for_scenario
from ..types import ForgeResult, Scenario


async def run_issue(
    client: AnthropicClient,
    model: str,
    repo_path: Path,
    issue_info: Dict[str, Any],
    similar_issue_candidates: List[Dict[str, Any]],
    *,
    custom_prompt: Optional[str] = None,
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
