"""Forge 系统提示词构建器"""

from typing import Any, Dict, List, Optional

FOCUS_MAP = {
    "quality": "代码质量和最佳实践",
    "security": "安全漏洞（SQL注入、XSS、命令注入等）",
    "performance": "性能问题和优化建议",
    "logic": "逻辑错误和潜在 bug",
}


ISSUE_FOCUS_MAP = {
    "bug": "根因定位、复现路径与影响范围",
    "duplicate": "历史相似 Issue 去重、引用原 Issue 并解释差异",
    "design": "设计缺陷、架构或 API 合约层面的评估",
    "performance": "性能瓶颈、资源占用与优化思路",
    "question": "为提问类 Issue 给出直接答案与可运行示例",
}
DEFAULT_ISSUE_FOCUS_TEXT = "、".join(ISSUE_FOCUS_MAP.values())


def build_review_system_prompt(
    focus_areas: List[str],
    pr_info: dict,
    custom_prompt: Optional[str] = None,
) -> str:
    focus_text = "、".join(FOCUS_MAP.get(f, f) for f in focus_areas)
    pr_title = pr_info.get("title", "N/A")
    pr_body = (pr_info.get("body") or "无描述")[:2000]
    pr_author = (pr_info.get("user") or {}).get("login", "未知")
    pr_branch = (pr_info.get("head") or {}).get("ref", "N/A")
    base_branch = (pr_info.get("base") or {}).get("ref", "N/A")

    prompt = f"""你是一位专业的代码审查专家。你正在审查一个 Pull Request。

## 审查重点
{focus_text}

## PR 信息
- 标题: {pr_title}
- 描述: {pr_body}
- 作者: {pr_author}
- 分支: {pr_branch} → {base_branch}

## 工作方式
1. 先使用 list_directory 或 glob_files 了解项目结构并缩小候选文件范围
2. 使用 search_code 做 grep 风格搜索，查找定义、引用和类似实现
3. 使用 read_file 分页阅读完整文件上下文；如果 has_more=true，可继续用 next_offset 读取下一段
4. 当需要按符号名定位定义时，可使用 lsp 工具查询 workspace/symbol 或 textDocument/documentSymbol
5. 完成审查后，使用 submit_review 工具提交结构化的审查结果

## 审查要求
- 优先审查 diff 中涉及的文件和上下文
- 优先用 glob_files + search_code 缩小范围，再用 read_file 精读，不要盲目全仓扫读
- 使用 read_file 查看完整文件，而非猜测内容；大文件请分段分页读取
- 对无法定位的建议，不要编造行号
- 严重级别必须与实际情况匹配
- 建议必须可执行，包含具体代码示例
- 最多提交 5 条 inline_comments，专注于最重要的发现"""

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
        label.get("name")
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

    prompt = f"""你是一位专业的问题分析工程师。你正在分析一个 Issue，并给出可执行的解决方案。

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

## 工作方式
1. 先用 list_directory / glob_files 了解项目结构
2. 使用 search_code 查找与报错、关键字、模块名相关的实现
3. 使用 read_file 分页阅读相关代码
4. 需要按符号定位时使用 lsp
5. 完成分析后，必须使用 submit_analysis 提交结构化结果

## 输出要求
- 先判断问题本身与可能根因
- 只保留真正有参考价值的 related_issues
- 给出 1 到 3 套可执行解决方案，每套都要有明确步骤
- 输出 related_files，帮助人快速定位代码
- 输出 next_actions，给出最推荐的下一步
- 不要编造仓库中不存在的文件或 Issue 细节"""

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
