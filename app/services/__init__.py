"""
Service layer modules that integrate with external systems and encapsulate
domain-specific workflows.
"""

from .gitea_client import GiteaClient
from .repo_manager import RepoManager
from .repo_registry import RepoRegistry
from .claude_analyzer import ClaudeAnalyzer
from .webhook_handler import WebhookHandler
from .auth_manager import AuthManager

__all__ = [
    "GiteaClient",
    "RepoManager",
    "RepoRegistry",
    "ClaudeAnalyzer",
    "WebhookHandler",
    "AuthManager",
]
