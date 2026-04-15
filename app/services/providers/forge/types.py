"""Forge 核心数据类型"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Scenario(str, Enum):
    REVIEW = "review"
    ISSUE = "issue"
    FIX = "fix"


@dataclass
class ForgeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def accumulate(self, other: "ForgeUsage") -> "ForgeUsage":
        return ForgeUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
        )


@dataclass
class ForgeToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ForgeToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class ForgeResult:
    success: bool
    scenario: Scenario
    structured_data: Optional[Dict[str, Any]] = None
    final_text: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    usage: ForgeUsage = field(default_factory=ForgeUsage)
    model: str = ""
    turns: int = 0
    tool_calls: int = 0
    error: Optional[str] = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_api_format(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
