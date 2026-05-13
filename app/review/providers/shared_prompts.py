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

    prompt = f"""{lang_instruction}你是一位专业的代码审查专家。请严格按以下步骤审查 Pull Request 的代码变更。

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

---

**审查步骤（按顺序执行）：**

Step 1 — 推断变更意图
分析 diff 的整体模式，用 1-2 句概括作者的核心目标。意图必须具体，不得泛化。
- 好的表述："修复 JWT exp 字段未校验导致刷新令牌永不过期的 bug"
- 不好的表述："改进了代码质量"、"修复了一些问题"

Step 2 — 生成 pr_overview_markdown（纯文字，不含 Mermaid）
包含：
- **意图**：Step 1 的结论（1-2 句）
- **风险等级**：`critical / high / medium / low / info` + 一句理由
  - critical：安全漏洞、数据丢失、生产崩溃
  - high：生产环境逻辑错误
  - medium：缺少错误处理、边界条件未覆盖
  - low：轻微改进机会
  - info：无明显缺陷，纯建议
- **变更范围**：涉及哪些模块/文件（1-2 句）

Step 3 — 按审查重点扫描问题
仅扫描 diff 中**新增或修改**的代码，结合 Step 1 的意图判断问题是否真实存在。

以下情况**不得输出评论**：
- 只描述代码做了什么，不指出缺陷
- 含"可能"、"也许"、"建议检查"等不确定措辞
- 命名、缩进、注释风格等格式问题
- `.md`、`.txt`、`.json`（配置）、`.yaml`、锁文件、生成产物
- UI 样式数值（字体大小、间距、颜色值）默认视为设计已确认

Step 4 — 构建 summary_markdown（问题表格）
问题标题必须包含**具体现象**，不得只写维度名称（如"安全问题"）。

```
| No. | 问题标题 | 建议 | 代码位置 |
|-----|---------|------|---------|
| 1   | JWT exp 字段未校验，令牌可能永不过期 | 在 refresh() 中检查 token.exp < time.time() | auth/token.py:45 |
```

若无问题：summary_markdown 填 `""`，inline_comments 填 `[]`，overall_severity 填 `"info"`。

---

**输出要求（必须严格遵守）：**
- 最终输出为**单个 JSON 对象**，不包含任何额外文本、注释或代码块标记
- `overall_severity`：critical / high / medium / low / info
- `inline_comments`：最多 10 条，仅记录 high/critical 问题，不需要凑满，无问题填 `[]`
- 行号使用**新版本行号**（new_line）标注新增/修改行，删除行使用 old_line；无法精确定位时省略该条
- 路径使用相对于仓库根目录的精确路径，不含 `./` 前缀
- `suggestion` 含代码时必须使用 Markdown 代码块（```语言 ... ```）
- 同一问题不得在 summary 表格和 inline_comments 中重复描述

JSON 结构：
{{
  "pr_overview_markdown": "**意图：** 修复 JWT exp 字段未校验的 bug\\n\\n**风险等级：** high — 令牌刷新后可能永不过期，影响认证安全\\n\\n**变更范围：** 修改了 auth/token.py 中的 refresh() 方法",
  "summary_markdown": "| No. | 问题标题 | 建议 | 代码位置 |\\n|---|---|---|---|\\n| 1 | JWT exp 未校验，刷新后令牌永不过期 | 添加 `if token.exp < time.time(): raise TokenExpiredError()` | auth/token.py:45 |",
  "overall_severity": "high",
  "inline_comments": [
    {{
      "path": "auth/token.py",
      "new_line": 45,
      "old_line": null,
      "severity": "high",
      "comment": "refresh() 未检查令牌是否已过期，攻击者可用旧令牌持续刷新获得永久访问权",
      "suggestion": "```python\\nif token.exp < time.time():\\n    raise TokenExpiredError('token has expired')\\n```"
    }}
  ]
}}
"""
    if custom_prompt and custom_prompt.strip():
        prompt += f"\n\n**额外审查要求：**\n{custom_prompt.strip()}"
    return prompt
