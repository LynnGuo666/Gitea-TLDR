"""Forge submit_review 工具 — 结构化审查结果提交

这是 Forge 最重要的创新：模型通过工具调用提交结构化结果，
而非从自由文本中暴力提取 JSON。
"""

from typing import Any, Dict

from . import ForgeTool


class SubmitReviewTool(ForgeTool):
    @property
    def name(self) -> str:
        return "submit_review"

    @property
    def description(self) -> str:
        return (
            "提交 PR 审查结果。当您完成代码审查后，调用此工具提交结构化的审查报告。"
            "此工具的参数即为最终审查结果，调用后审查将结束。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pr_overview_markdown": {
                    "type": "string",
                    "description": (
                        "第一条评论内容：变更意图说明（1-2句）、Mermaid 流程图、整体风险等级。"
                        "必须包含 Mermaid 图，颜色规则：fill 与 color 同时指定。"
                    ),
                },
                "summary_markdown": {
                    "type": "string",
                    "description": (
                        "第二条评论内容：Markdown 格式的问题表格 "
                        "（| No. | 问题标题 | 建议 | 代码位置 |）。"
                        "若无问题则填空字符串。"
                    ),
                },
                "overall_severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "info"],
                    "description": "整体严重程度",
                },
                "inline_comments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径（相对于仓库根目录）",
                            },
                            "new_line": {
                                "type": ["integer", "null"],
                                "description": "新文件行号",
                            },
                            "old_line": {
                                "type": ["integer", "null"],
                                "description": "旧文件行号",
                            },
                            "severity": {
                                "type": ["string", "null"],
                                "enum": ["critical", "high", "medium", "low", "info"],
                            },
                            "comment": {"type": "string", "description": "评论内容"},
                            "suggestion": {
                                "type": ["string", "null"],
                                "description": "修复建议（含代码时使用 Markdown 代码块）",
                            },
                        },
                        "required": ["path", "comment"],
                    },
                    "description": "行级批注列表，最多 10 条，专注最重要发现，无问题时填 []",
                },
            },
            "required": [
                "pr_overview_markdown",
                "summary_markdown",
                "overall_severity",
            ],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path) -> str:
        return "Review submitted successfully."
