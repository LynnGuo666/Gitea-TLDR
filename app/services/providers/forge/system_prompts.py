"""Forge 系统提示词构建器"""

from typing import List, Optional

FOCUS_MAP = {
    "quality": "代码质量和最佳实践",
    "security": "安全漏洞（SQL注入、XSS、命令注入等）",
    "performance": "性能问题和优化建议",
    "logic": "逻辑错误和潜在 bug",
}


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


MAX_DIFF_BYTES = 200_000


def build_initial_message(diff_content: str) -> str:
    if len(diff_content.encode("utf-8")) > MAX_DIFF_BYTES:
        diff_content = diff_content[:MAX_DIFF_BYTES] + "\n\n... (diff 过长，已截断)"
    return f"请审查以下 PR 的代码变更：\n\n```diff\n{diff_content}\n```"
