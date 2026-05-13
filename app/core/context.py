"""
Application context holding long-lived service instances.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.gitea.client import GiteaClient
from app.gitea.auth import AuthManager
from app.gitea.repo_manager import RepoManager
from app.gitea.repo_registry import RepoRegistry
from app.review import ReviewEngine, WebhookHandler

if TYPE_CHECKING:
    from app.core.database import Database


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
