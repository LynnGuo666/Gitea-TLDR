"""Forge Agentic Loop 引擎

参照 claw-code-agent 的 LocalCodingAgent.run() 模式：
  for turn_index in range(1, max_turns + 1):
      turn = query_model(...)
      if not turn.tool_calls:
          return result
      tool_results = execute_tools(turn.tool_calls)
      messages.append(tool_results)
      continue
"""

import logging
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Union

from .api_client import AnthropicClient
from .types import (
    ForgeResult,
    ForgeToolCall,
    ForgeToolResult,
    ForgeUsage,
    Scenario,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 5

ToolExecutor = Callable[[ForgeToolCall, Path], Awaitable[ForgeToolResult]]


class ForgeEngine:
    def __init__(
        self,
        client: AnthropicClient,
        model: str,
        max_turns: int = DEFAULT_MAX_TURNS,
    ):
        self.client = client
        self.model = model
        self.max_turns = max_turns

    async def run(
        self,
        system_prompt: str,
        initial_message: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        repo_path: Path,
        *,
        scenario: Scenario = Scenario.REVIEW,
        stop_sequences: Optional[List[str]] = None,
        temperature: Optional[float] = None,
    ) -> ForgeResult:
        messages: List[dict] = [{"role": "user", "content": initial_message}]
        total_usage = ForgeUsage()
        accumulated_text = ""
        total_tool_calls = 0
        turns = 0

        for turn_index in range(1, self.max_turns + 1):
            turns = turn_index

            try:
                response_data, turn_usage = await self.client.create_message(
                    model=self.model,
                    messages=messages,
                    system=system_prompt,
                    tools=[t.to_api_format() for t in tools],
                    stop_sequences=stop_sequences,
                    temperature=temperature,
                )
            except PermissionError as e:
                return ForgeResult(
                    success=False,
                    scenario=scenario,
                    error=str(e),
                    turns=turn_index,
                    usage=total_usage,
                    model=self.model,
                )
            except RuntimeError as e:
                return ForgeResult(
                    success=False,
                    scenario=scenario,
                    error=str(e),
                    turns=turn_index,
                    usage=total_usage,
                    model=self.model,
                )
            except Exception as e:
                logger.error(f"Forge API 调用异常 (turn {turn_index}): {e}")
                return ForgeResult(
                    success=False,
                    scenario=scenario,
                    error=f"API 调用失败: {e}",
                    turns=turn_index,
                    usage=total_usage,
                    model=self.model,
                )

            total_usage = total_usage.accumulate(turn_usage)
            content_blocks = response_data.get("content", [])
            turn_text = self.client.parse_text_content(content_blocks)
            if turn_text:
                accumulated_text += turn_text

            tool_calls = self.client.parse_tool_calls(content_blocks)

            submit_result = self._extract_submit_result(tool_calls, scenario)
            if submit_result is not None:
                total_tool_calls += len(tool_calls)
                return ForgeResult(
                    success=True,
                    scenario=scenario,
                    structured_data=submit_result,
                    final_text=accumulated_text,
                    messages=messages
                    + [{"role": "assistant", "content": content_blocks}],
                    usage=total_usage,
                    model=self.model,
                    turns=turn_index,
                    tool_calls=total_tool_calls,
                )

            if not tool_calls:
                return ForgeResult(
                    success=True,
                    scenario=scenario,
                    final_text=accumulated_text,
                    messages=messages
                    + [{"role": "assistant", "content": content_blocks}],
                    usage=total_usage,
                    model=self.model,
                    turns=turn_index,
                    tool_calls=total_tool_calls,
                )

            total_tool_calls += len(tool_calls)
            messages.append({"role": "assistant", "content": content_blocks})

            tool_results: List[ForgeToolResult] = []
            for tc in tool_calls:
                try:
                    result = await tool_executor(tc, repo_path)
                    tool_results.append(result)
                except Exception as e:
                    logger.error(f"工具执行异常 {tc.name}: {e}")
                    tool_results.append(
                        ForgeToolResult(
                            tool_call_id=tc.id,
                            content=f"工具执行错误: {e}",
                            is_error=True,
                        )
                    )

            tool_result_blocks = []
            for tr in tool_results:
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tr.tool_call_id,
                        "content": tr.content,
                        "is_error": tr.is_error,
                    }
                )
            messages.append({"role": "user", "content": tool_result_blocks})

        logger.warning(f"Forge 达到最大轮次限制 ({self.max_turns})")
        return ForgeResult(
            success=False,
            scenario=scenario,
            final_text=accumulated_text,
            messages=messages,
            usage=total_usage,
            model=self.model,
            turns=self.max_turns,
            tool_calls=total_tool_calls,
            error=f"达到最大轮次限制 ({self.max_turns})",
        )

    def _extract_submit_result(
        self,
        tool_calls: List[ForgeToolCall],
        scenario: Scenario,
    ) -> Optional[dict]:
        submit_tool_names = {
            Scenario.REVIEW: "submit_review",
            Scenario.ISSUE: "submit_analysis",
            Scenario.FIX: "submit_fix",
        }
        target = submit_tool_names.get(scenario)
        if not target:
            return None
        for tc in tool_calls:
            if tc.name == target:
                return tc.arguments
        return None
