"""CLI provider 共用的审查 prompt 构建工具"""

import re
from typing import List, Optional

FOCUS_MAP = {
    "quality": "代码质量和最佳实践",
    "security": "安全漏洞（SQL注入、XSS、命令注入等）",
    "performance": "性能问题和优化建议",
    "logic": "逻辑错误和潜在 bug",
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _detect_language_instruction(pr_info: dict) -> str:
    title = pr_info.get("title") or ""
    body = pr_info.get("body") or ""
    if _CJK_RE.search(title) or _CJK_RE.search(body):
        return "请用中文回复。\n\n"
    return "Please reply in English.\n\n"


def build_cli_review_prompt(
    focus_areas: List[str],
    pr_info: dict,
    diff_content: str,
    custom_prompt: Optional[str] = None,
) -> str:
    """构建 CLI provider 共用的 PR 审查 prompt。

    diff_content 应由调用方在传入前完成截断。
    """
    lang_instruction = _detect_language_instruction(pr_info)
    focus_text = "、".join([FOCUS_MAP.get(f, f) for f in focus_areas])

    prompt = f"""{lang_instruction}你是一位专业的代码审查专家。请按以下步骤审查 Pull Request 的代码变更。

**PR 信息：**
- 标题: {pr_info.get("title", "N/A")}
- 描述: {pr_info.get("body", "N/A")}
- 作者: {pr_info.get("user", {}).get("login", "N/A")}

**审查重点：**
{focus_text}

**代码变更（diff）：**
```diff
{diff_content}
```

**审查步骤：**

Step 1 — 推断变更意图
分析 diff 的整体模式，用 1-2 句概括作者目标，例如："修复 JWT 刷新后用户被强制登出的问题"。

Step 2 — 生成 pr_overview_markdown
包含以下内容（纯文字，无 Mermaid）：
- 变更意图（Step 1 推断结果）
- 整体风险：`critical / high / medium / low / info` + 一句理由
- 变更范围概述（涉及哪些模块/文件）

Step 3 — 按审查重点扫描问题
仅扫描 diff 中新增/修改的代码，聚焦已指定的审查维度。

Step 4 — 构建 summary_markdown（问题表格）
若发现问题，使用以下格式：
```
| No. | 问题标题 | 建议 | 代码位置 |
|-----|---------|------|---------|
| 1   | ...     | ...  | path/to/file.py:123 |
```
若无问题，summary_markdown 填空字符串 ""。

**输出要求（必须严格遵守）：**
- 最终输出为单个 JSON 对象，不包含额外文本、注释或代码块标记
- `overall_severity` 取值：critical/high/medium/low/info
- `inline_comments` 最多 10 条，专注最重要发现，无问题时填 []
- 行号必须与 diff 一致，无法定位时省略该条
- `suggestion` 若含代码必须使用 Markdown 代码块（```语言...```）

JSON 结构：
{{
  "pr_overview_markdown": "## 变更概览\\n**意图：** ...\\n**风险：** medium — ...",
  "summary_markdown": "| No. | 问题标题 | 建议 | 代码位置 |\\n|---|---|---|---|\\n| 1 | ... | ... | path:123 |",
  "overall_severity": "medium",
  "inline_comments": [
    {{
      "path": "app/main.py",
      "new_line": 123,
      "old_line": null,
      "severity": "high",
      "comment": "描述问题与影响",
      "suggestion": "建议修改为：\\n```python\\nresult = safe_function(user_input)\\n```"
    }}
  ]
}}
"""
    if custom_prompt and custom_prompt.strip():
        prompt += f"\n\n**额外审查要求：**\n{custom_prompt.strip()}"
    return prompt
