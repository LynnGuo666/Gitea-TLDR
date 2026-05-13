"""Forge submit_analysis 工具。"""

from __future__ import annotations

from typing import Any, Dict

from . import ForgeTool


class SubmitAnalysisTool(ForgeTool):
    @property
    def name(self) -> str:
        return "submit_analysis"

    @property
    def description(self) -> str:
        return "提交结构化的 Issue 分析结果。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary_markdown": {
                    "type": "string",
                    "description": "Issue 分析摘要，使用 Markdown。",
                },
                "overall_severity": {
                    "type": ["string", "null"],
                    "enum": ["critical", "high", "medium", "low", "info", None],
                    "description": "问题严重程度。",
                },
                "related_issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "integer"},
                            "title": {"type": "string"},
                            "state": {"type": "string"},
                            "url": {"type": "string"},
                            "similarity_reason": {"type": "string"},
                            "suggested_reference": {"type": "string"},
                        },
                        "required": [
                            "number",
                            "title",
                            "state",
                            "url",
                            "similarity_reason",
                            "suggested_reference",
                        ],
                    },
                },
                "solution_suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "steps": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["title", "summary", "steps"],
                    },
                },
                "related_files": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "next_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "summary_markdown",
                "overall_severity",
                "related_issues",
                "solution_suggestions",
                "related_files",
                "next_actions",
            ],
        }

    async def execute(self, arguments: Dict[str, Any], repo_path) -> str:
        del arguments, repo_path
        return "Issue analysis submitted successfully."
