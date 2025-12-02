"""
Core utilities and configuration for the backend application.
"""

from .config import settings  # re-export for convenience
from .version import (
    __version__,
    get_version_banner,
    get_version_info,
    get_changelog,
    get_all_changelogs,
)

__all__ = [
    "settings",
    "__version__",
    "get_version_banner",
    "get_version_info",
    "get_changelog",
    "get_all_changelogs",
]
