"""Forge 系统提示词构建器"""

import re
from typing import Any, Dict, List, Optional

from ..shared_prompts import FOCUS_MAP

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _detect_language_instruction(pr_info: dict) -> str:
    title = pr_info.get("title") or ""
    body = pr_info.get("body") or ""
    if _CJK_RE.search(title) or _CJK_RE.search(body):
        return "请用中文回复。\n\n"
    return "Please reply in English.\n\n"


ISSUE_FOCUS_MAP = {
    "bug": "根因定位、复现路径与影响范围",
    "duplicate": "历史相似 Issue 去重、引用原 Issue 并解释差异",
    "design": "设计缺陷、架构或 API 合约层面的评估",
    "performance": "性能瓶颈、资源占用与优化思路",
    "question": "为提问类 Issue 给出直接答案与可运行示例",
}
DEFAULT_ISSUE_FOCUS_TEXT = "、".join(ISSUE_FOCUS_MAP.values())


_DEFAULT_REVIEW_FOCUS_TEXT = "、".join(FOCUS_MAP.values())


def build_review_system_prompt(
    focus_areas: List[str],
    pr_info: dict,
    custom_prompt: Optional[str] = None,
) -> str:
    lang_instruction = _detect_language_instruction(pr_info)
    if focus_areas:
        focus_text = "、".join(FOCUS_MAP.get(f, f) for f in focus_areas)
    else:
        focus_text = _DEFAULT_REVIEW_FOCUS_TEXT

    pr_title = pr_info.get("title", "N/A")
    pr_body = (pr_info.get("body") or "无描述")[:2000]
    pr_author = (pr_info.get("user") or {}).get("login", "未知")
    pr_branch = (pr_info.get("head") or {}).get("ref", "N/A")
    base_branch = (pr_info.get("base") or {}).get("ref", "N/A")

    prompt = f"""{lang_instruction}你是一位专业的代码审查专家。你正在审查一个 Pull Request。

## PR 信息
- 标题: {pr_title}
- 描述: {pr_body}
- 作者: {pr_author}
- 分支: {pr_branch} → {base_branch}

## 审查重点
{focus_text}

## 工作步骤（按顺序执行）

**Step 1 — 了解项目结构**
使用 list_directory 或 glob_files 了解项目结构，缩小候选文件范围。

**Step 2 — 读取上下文**
使用 search_code 查找定义、引用和类似实现；使用 read_file 分页阅读涉及文件的完整上下文（has_more=true 时继续读取）。需要按符号定位时，使用 lsp 工具。

**Step 3 — 推断变更意图**
基于 diff 整体模式，用 1-2 句概括作者的目标，例如：
- "修复 JWT 令牌刷新后用户被强制登出的问题"
- "将分页逻辑从 offset 模式重构为 cursor 模式以提升性能"
- "为用户注册接口添加邮箱唯一性校验"

**Step 4 — 生成 pr_overview_markdown（第一条评论内容）**
必须包含以下三部分：

1. **变更意图**：Step 3 中推断的意图（1-2 句）
2. **Mermaid 流程图**（始终生成，1-2 个）：
   - 使用 `flowchart` 或 `sequenceDiagram` 展示关键变更的业务流或技术调用链
   - 聚焦本次变更涉及的核心路径，不要画整个系统
   - **颜色规则**：fill 与 color 必须同时指定，确保深浅主题可读
     - 推荐组合：`fill:#c8e6c9,color:#1a5e20`（绿）、`fill:#bbdefb,color:#0d47a1`（蓝）
     - `fill:#fff3e0,color:#e65100`（橙）、`fill:#f3e5f5,color:#7b1fa2`（紫）
   - 用 style 或 classDef 高亮本次变更的关键节点
3. **整体风险**：`critical / high / medium / low / info` + 一句理由

**Step 5 — 按审查重点扫描问题**
按照"审查重点"中的维度逐一扫描，优先关注 diff 中的新增/修改代码。

**Step 6 — 构建 summary_markdown（第二条评论内容）**
若发现问题，输出以下格式的问题表格：

```
| No. | 问题标题 | 建议 | 代码位置 |
|-----|---------|------|---------|
| 1   | ...     | ...  | `path/to/file.py:123` |
```

若无问题，summary_markdown 填空字符串 `""`，inline_comments 填 `[]`。

**Step 7 — 调用 submit_review 提交**
提交包含 pr_overview_markdown、summary_markdown、overall_severity 和 inline_comments 的审查结果。

## inline_comments 规则
- 最多 10 条，专注于最重要的发现，**无需强制填满**
- 行号必须来自实际读取的文件，不得编造
- suggestion 字段若含代码必须使用 Markdown 代码块

## 严禁行为
- 禁止编造不存在于 diff 的行号或文件路径
- 禁止对无法确定的问题给出"可能有问题"等模糊建议
- 禁止因格式/命名风格问题将 severity 提升至 high 以上
- 禁止在未读取文件的情况下评论文件内容"""

    if custom_prompt and custom_prompt.strip():
        prompt += f"\n\n## 额外审查要求\n{custom_prompt.strip()}"

    return prompt


def build_issue_system_prompt(
    issue_info: Dict[str, Any],
    similar_issue_candidates: List[Dict[str, Any]],
    custom_prompt: Optional[str] = None,
    focus_areas: Optional[List[str]] = None,
) -> str:
    issue_title = issue_info.get("title", "N/A")
    issue_body = (issue_info.get("body") or "无描述")[:3000]
    issue_author = (issue_info.get("user") or {}).get("login", "未知")
    labels = issue_info.get("labels") or []
    label_names = [
        str(label.get("name"))
        for label in labels
        if isinstance(label, dict) and label.get("name")
    ]
    label_text = "、".join(label_names) if label_names else "无"

    candidate_lines: List[str] = []
    if similar_issue_candidates:
        for item in similar_issue_candidates:
            candidate_lines.append(
                "- #{number} {title} [{state}] | 标签: {labels} | 初步相似原因: {reason}".format(
                    number=item.get("number", "?"),
                    title=item.get("title", "无标题"),
                    state=item.get("state", "unknown"),
                    labels="、".join(item.get("label_names", [])) or "无",
                    reason=item.get("score_reason", "关键词重合"),
                )
            )
    else:
        candidate_lines.append("- 无候选相似 Issue")

    focus_text = DEFAULT_ISSUE_FOCUS_TEXT
    if focus_areas:
        mapped = [ISSUE_FOCUS_MAP.get(f, f) for f in focus_areas if f]
        if mapped:
            focus_text = "、".join(mapped)

    prompt = f"""你是一位专业的问题分析工程师。你正在分析一个 Issue，并给出可执行的修复方案。

## 分析重点
{focus_text}

## 当前 Issue
- 标题: {issue_title}
- 作者: {issue_author}
- 标签: {label_text}
- 描述:
{issue_body}

## 相似 Issue 候选
{chr(10).join(candidate_lines)}

## 工作步骤（按顺序执行）

**Step 1 — 了解项目结构**
使用 list_directory / glob_files 了解项目结构，定位与 Issue 相关的模块。

**Step 2 — 提出可证伪假设**
在读取任何代码之前，根据 Issue 描述提出 3-5 个可证伪的根因假设。每条假设必须对应一个具体的观测点，格式如下：
- "假设A：token 刷新时未校验 exp 字段 → 验证方法：读取 auth/token.py 中的 refresh() 实现"
- "假设B：并发请求导致 session 覆盖 → 验证方法：检查 session 写入是否有锁保护"

**Step 3 — 代码级验证**
对每个假设，使用 search_code / read_file / lsp 进行验证或推翻：
- 已证实：找到了支持该假设的代码证据
- 已推翻：找到了反驳该假设的代码证据
- 无法确认：缺乏足够证据，不得基于此假设给出修复建议

**Step 4 — 基于已证实假设给出修复方案**
仅基于 Step 3 中已证实的假设，给出 1-3 套可执行修复方案，每套包含：
- 方案标题与简述
- 明确的步骤（含具体代码示例）
- 风险说明（如有）

**Step 5 — 调用 submit_analysis 提交结构化结果**

## 输出要求
- related_issues：只保留真正有参考价值的相似 Issue
- solution_suggestions：基于已证实假设的 1-3 套方案，每套有明确步骤
- related_files：帮助快速定位代码的文件列表
- next_actions：最推荐的下一步行动
- 禁止编造仓库中不存在的文件路径或 Issue 细节
- 禁止基于未经验证的假设给出修复方案"""

    if custom_prompt and custom_prompt.strip():
        prompt += f"\n\n## 额外要求\n{custom_prompt.strip()}"

    return prompt


MAX_DIFF_BYTES = 200_000


def build_initial_message(diff_content: str) -> str:
    if len(diff_content.encode("utf-8")) > MAX_DIFF_BYTES:
        diff_content = diff_content[:MAX_DIFF_BYTES] + "\n\n... (diff 过长，已截断)"
    return f"请审查以下 PR 的代码变更：\n\n```diff\n{diff_content}\n```"


def build_issue_initial_message(
    issue_info: Dict[str, Any],
    similar_issue_candidates: List[Dict[str, Any]],
) -> str:
    issue_number = issue_info.get("number", "N/A")
    issue_title = issue_info.get("title", "无标题")
    issue_body = issue_info.get("body") or "无描述"
    if len(issue_body.encode("utf-8")) > MAX_DIFF_BYTES:
        issue_body = issue_body[:MAX_DIFF_BYTES] + "\n\n... (Issue 描述过长，已截断)"

    candidate_lines = []
    for item in similar_issue_candidates:
        candidate_lines.append(
            "- #{number} {title}: {body}".format(
                number=item.get("number", "?"),
                title=item.get("title", "无标题"),
                body=(item.get("body_excerpt") or "无描述")[:300],
            )
        )

    candidate_text = "\n".join(candidate_lines) if candidate_lines else "- 无"

    return (
        f"请分析以下 Issue，并给出解决方案。\n\n"
        f"## 当前 Issue\n"
        f"- 编号: #{issue_number}\n"
        f"- 标题: {issue_title}\n\n"
        f"### 描述\n{issue_body}\n\n"
        f"## 相似 Issue 候选\n{candidate_text}"
    )
