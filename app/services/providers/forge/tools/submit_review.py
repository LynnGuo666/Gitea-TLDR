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
                "summary_markdown": {
                    "type": "string",
                    "description": "Markdown 格式的审查总结",
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
                                "description": "修复建议",
                            },
                        },
                        "required": ["path", "comment"],
                    },
                    "description": "行级审查评论列表",
                },
            },
            "required": ["summary_markdown", "overall_severity"],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path) -> str:
        return "Review submitted successfully."
