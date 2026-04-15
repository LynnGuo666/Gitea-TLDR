"""PR 审查场景 — Forge 的首个场景"""

import logging
from pathlib import Path
from typing import List, Optional

from ..api_client import AnthropicClient
from ..engine import ForgeEngine
from ..system_prompts import build_review_system_prompt, build_initial_message
from ..tools import get_tools_for_scenario, get_tool_executor
from ..types import ForgeResult, Scenario

logger = logging.getLogger(__name__)


async def run_review(
    client: AnthropicClient,
    model: str,
    repo_path: Path,
    diff_content: str,
    focus_areas: List[str],
    pr_info: dict,
    *,
    custom_prompt: Optional[str] = None,
    max_turns: int = 5,
    temperature: Optional[float] = None,
) -> ForgeResult:
    scenario = Scenario.REVIEW
    system_prompt = build_review_system_prompt(
        focus_areas=focus_areas,
        pr_info=pr_info,
        custom_prompt=custom_prompt,
    )
    initial_message = build_initial_message(diff_content)
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
