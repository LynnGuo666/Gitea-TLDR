from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.issue_analysis_service import IssueAnalysisService


class DummyGiteaClient:
    async def list_issues(self, owner: str, repo: str, state: str = "all", limit: int = 100):
        del owner, repo, state, limit
        return [
            {
                "number": 10,
                "title": "API timeout on sync",
                "body": "sync api timeout when queue is large",
                "state": "open",
                "html_url": "https://example.com/issues/10",
                "labels": [{"name": "bug"}, {"name": "sync"}],
            },
            {
                "number": 11,
                "title": "Refactor navbar",
                "body": "visual cleanup only",
                "state": "closed",
                "html_url": "https://example.com/issues/11",
                "labels": [{"name": "ui"}],
            },
            {
                "number": 12,
                "title": "sync timeout when queue backlog grows",
                "body": "api timeout and queue retry problem",
                "state": "closed",
                "html_url": "https://example.com/issues/12",
                "labels": [{"name": "bug"}, {"name": "sync"}],
            },
        ]


class ChineseGiteaClient:
    async def list_issues(self, owner: str, repo: str, state: str = "all", limit: int = 100):
        del owner, repo, state, limit
        return [
            {
                "number": 100,
                "title": "登录 时 发 生 接口 超时",
                "body": "登录接口在高并发时超时断连",
                "state": "open",
                "html_url": "https://example.com/issues/100",
                "labels": [{"name": "bug"}],
            },
            {
                "number": 101,
                "title": "UI 样式调整",
                "body": "更新导航栏颜色",
                "state": "closed",
                "html_url": "https://example.com/issues/101",
                "labels": [{"name": "ui"}],
            },
        ]


def test_find_similar_issue_candidates_skips_current_issue_and_prefers_keyword_overlap():
    service = IssueAnalysisService(
        gitea_client=DummyGiteaClient(),
        repo_manager=None,  # type: ignore[arg-type]
        database=None,
    )
    current_issue = {
        "number": 10,
        "title": "sync api timeout on queue backlog",
        "body": "api timeout when sync queue backlog grows",
        "labels": [{"name": "bug"}, {"name": "sync"}],
    }

    result = asyncio.run(
        service._find_similar_issue_candidates("owner", "repo", current_issue)
    )

    assert [item["number"] for item in result] == [12]
    assert result[0]["score_reason"]


def test_extract_keywords_handles_chinese_text():
    service = IssueAnalysisService(
        gitea_client=DummyGiteaClient(),
        repo_manager=None,  # type: ignore[arg-type]
        database=None,
    )

    tokens = service._extract_keywords("登录接口在高并发时超时断连")

    assert tokens, "中文分词不应返回空集"
    # 命中至少一个有效关键词（具体返回依赖 jieba/fallback，不硬编码）
    assert any(len(t) >= 2 for t in tokens)


def test_find_similar_issue_candidates_matches_chinese_issues():
    service = IssueAnalysisService(
        gitea_client=ChineseGiteaClient(),
        repo_manager=None,  # type: ignore[arg-type]
        database=None,
    )
    current_issue = {
        "number": 200,
        "title": "登录接口偶尔超时",
        "body": "用户登录时出现接口超时异常",
        "labels": [{"name": "bug"}],
    }

    result = asyncio.run(
        service._find_similar_issue_candidates("owner", "repo", current_issue)
    )

    assert any(item["number"] == 100 for item in result)
    # UI 与登录主题不相关，应被过滤
    assert all(item["number"] != 101 for item in result)
