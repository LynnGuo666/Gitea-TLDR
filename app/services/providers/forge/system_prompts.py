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
1. 使用 read_file 工具阅读仓库中的文件来理解上下文
2. 使用 search_code 工具搜索代码模式来发现潜在问题
3. 使用 list_directory 工具浏览项目结构来理解架构
4. 完成审查后，使用 submit_review 工具提交结构化的审查结果

## 审查要求
- 优先审查 diff 中涉及的文件和上下文
- 使用 read_file 查看完整文件，而非猜测内容
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
