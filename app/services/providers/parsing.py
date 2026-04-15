"""
共享解析工具 — 从现有 Provider 抽取

从 claude_code.py 和 codex_cli.py 中提取的通用解析逻辑，
供 Forge 和现有 Provider 共同使用。

抽取的方法：
- extract_json_payload: 从文本中提取 JSON 对象
- scan_json_object: 深度追踪扫描 JSON（处理嵌套括号和字符串）
- parse_inline_comment: 将原始字典解析为 InlineComment
- coerce_int: 安全地将值转换为整数
- extract_actionable_error: 从 stderr/stdout 提取可操作的错误信息
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from .base import InlineComment

logger = logging.getLogger(__name__)


def extract_json_payload(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 JSON 对象

    支持多种格式：
    - 纯 JSON 对象
    - 包裹在 ```json ... ``` 中
    - 嵌入在 Markdown 文本中

    策略优先级：
    1. 直接 JSON 解析
    2. 从 ```json 代码块中提取（使用 scan_json_object 避免嵌套截断）
    3. 从文本中找到第一个完整 JSON 对象（使用 scan_json_object）

    注意：Forge 的首选路径是通过 submit_review 工具获取结构化数据，
    此函数仅作为降级兜底。
    """
    if not text or not text.strip():
        return None

    text_stripped = text.strip()
    try:
        result = json.loads(text_stripped)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    for code_block_match in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text):
        block_text = code_block_match.group(1).strip()
        if not block_text.startswith("{"):
            continue
        parsed = scan_json_object(block_text)
        if parsed is not None:
            return parsed
    logger.debug("JSON解析失败（code block）")

    start = text.find("{")
    if start != -1:
        parsed = scan_json_object(text[start:])
        if parsed is not None:
            return parsed

    return None


def scan_json_object(text: str) -> Optional[Dict[str, Any]]:
    """从文本开头扫描并解析第一个完整的 JSON 对象

    正确处理嵌套括号和字符串，避免简单的 find/rfind 导致的括号错位问题。
    这比 codex_cli 中使用的 find/rfind 方法更健壮。
    """
    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[: i + 1])
                except json.JSONDecodeError:
                    logger.debug("JSON解析失败（brace scan）")
                break

    return None


def parse_inline_comment(item: Dict[str, Any]) -> Optional[InlineComment]:
    """将原始字典解析为 InlineComment

    处理字段名变体（不同 Provider 可能返回不同格式）：
    - path / file
    - comment / body / message
    - new_line / line (when line_type == "new")
    - old_line / line (when line_type == "old")
    - severity / level
    - suggestion / recommended_fix
    """
    if not isinstance(item, dict):
        return None

    path = str(item.get("path") or item.get("file") or "").strip()
    comment = str(
        item.get("comment") or item.get("body") or item.get("message") or ""
    ).strip()
    if not path or not comment:
        return None

    line_type = (item.get("line_type") or "new").lower()
    new_line = coerce_int(
        item.get("new_line") or (item.get("line") if line_type == "new" else None)
    )
    old_line = coerce_int(
        item.get("old_line") or (item.get("line") if line_type == "old" else None)
    )

    severity = (
        (
            str(item.get("severity")).strip()
            if isinstance(item.get("severity"), str)
            else item.get("severity")
        )
        if item.get("severity") is not None
        else None
    )

    suggestion = (
        (
            str(item.get("suggestion")).strip()
            if isinstance(item.get("suggestion"), str)
            else item.get("suggestion")
        )
        if item.get("suggestion") is not None
        else None
    )

    # 也尝试 alternative 字段名
    severity = severity or item.get("level")
    suggestion = suggestion or item.get("recommended_fix")

    return InlineComment(
        path=path,
        comment=comment,
        new_line=new_line,
        old_line=old_line,
        severity=severity,
        suggestion=suggestion,
    )


def coerce_int(value: Any) -> Optional[int]:
    """安全地将值转换为整数

    处理 None、空字符串、浮点数等情况。
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value == int(value):
        return int(value)
    return None


def extract_actionable_error(stderr_text: str, stdout_text: str) -> str:
    """从 stderr/stdout 输出中提取可操作的错误信息

    合并 stdout/providers 中的两个版本，取最严格的匹配优先。
    """
    combined = "\n".join(
        part for part in [stderr_text.strip(), stdout_text.strip()] if part.strip()
    )
    if not combined:
        return ""

    combined = re.sub(r"\x1b\[[0-9;]*m", "", combined)

    for pattern in [
        r"ERROR:\s*unexpected status[^\n]*",
        r"unexpected status\s+\d{3}[^\n]*",
        r"Error:\s*[^\n]*",
        r"ERROR:\s*[^\n]*",
    ]:
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()

    lines = [line.strip() for line in combined.splitlines() if line.strip()]

    filtered = [
        line
        for line in lines
        if "Warning: no last agent message" not in line
        and not line.startswith("Reconnecting...")
        and "OpenAI Codex" not in line
        and "research preview" not in line
        and line != "--------"
        and "mcp startup: no servers" not in line
    ]

    if filtered:
        return filtered[-1]
    if lines:
        return lines[-1]
    return ""
