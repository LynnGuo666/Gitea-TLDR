"""
Forge — Agentic Review Engine

基于 Anthropic Messages API 的代理审查引擎。
参照 claw-code-agent 的 agentic loop 模式，提供：
- Agentic Loop（模型可主动调用工具获取上下文）
- 结构化输出（submit_* 工具调用，非暴力 JSON 解析）
- 多场景支持（review → issue → fix）
"""

from .provider import ForgeProvider
from .types import (
    ForgeResult,
    ForgeToolCall,
    ForgeToolResult,
    ForgeUsage,
    Scenario,
    ToolDefinition,
)

__all__ = [
    "ForgeProvider",
    "ForgeResult",
    "ForgeToolCall",
    "ForgeToolResult",
    "ForgeUsage",
    "Scenario",
    "ToolDefinition",
]
