"""
Application context holding long-lived service instances.
"""

from dataclasses import dataclass
from typing import Optional

from app.services import (
    GiteaClient,
    RepoManager,
    RepoRegistry,
    ReviewEngine,
    WebhookHandler,
    AuthManager,
)


@dataclass
class AppContext:
    """Container for backend service objects used by the API layer."""

    gitea_client: GiteaClient
    repo_manager: RepoManager
    review_engine: ReviewEngine
    webhook_handler: WebhookHandler
    repo_registry: RepoRegistry
    auth_manager: AuthManager
    database: Optional["Database"] = None

    def __post_init__(self):
        # 避免循环导入
        from app.core.database import Database

        # 类型标注用于IDE提示
        self.database: Optional[Database]
