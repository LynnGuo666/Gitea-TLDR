"""
Application context holding long-lived service instances.
"""
from dataclasses import dataclass
from app.services import (
    GiteaClient,
    RepoManager,
    RepoRegistry,
    ClaudeAnalyzer,
    WebhookHandler,
)


@dataclass
class AppContext:
    """Container for backend service objects used by the API layer."""

    gitea_client: GiteaClient
    repo_manager: RepoManager
    claude_analyzer: ClaudeAnalyzer
    webhook_handler: WebhookHandler
    repo_registry: RepoRegistry
