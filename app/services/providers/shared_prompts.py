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

    prompt = f"""{lang_instruction}请审查以下Pull Request的代码变更。

**PR信息：**
- 标题: {pr_info.get("title", "N/A")}
- 描述: {pr_info.get("body", "N/A")}
- 作者: {pr_info.get("user", {}).get("login", "N/A")}

**审查重点：**
{focus_text}

**代码变更（diff）：**
```diff
{diff_content}
```

请完成以下审查任务：
1. **总体评价**：描述本次变更的整体风险、积极影响
2. **发现的问题**：按严重程度列出（严重/中等/轻微），解释原因
3. **改进建议**：给出可执行的修改建议
4. **优点**：指出值得保留或学习的实现

输出要求（必须严格遵守）：
- 最终输出为单个JSON对象，不要包含额外文本、注释或代码块标记
- `summary_markdown` 字段使用Markdown编写上述内容，结构清晰
- `overall_severity` 取值：critical/high/medium/low/info
- `inline_comments` 最多5条，逐条包含精确的 `path`、`new_line` (新增行号) 或 `old_line` (删除行号)、`comment`，可选 `suggestion` 与 `severity`
- `suggestion` 字段如果包含代码，必须使用 Markdown 代码块格式（```语言...```）
- 对无法定位的建议，省略该条，确保所有行号与diff一致

JSON结构示例：
{{
  "summary_markdown": "### 总体评价\\n...",
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
