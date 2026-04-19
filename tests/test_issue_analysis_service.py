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
