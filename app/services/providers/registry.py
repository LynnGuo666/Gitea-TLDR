"""
Provider 注册表
"""

import logging
from typing import Dict, List, Optional, Type

from .base import ReviewProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """管理所有已注册的审查 Provider"""

    def __init__(self) -> None:
        self._providers: Dict[str, Type[ReviewProvider]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        from .claude_code import ClaudeCodeProvider
        from .codex_cli import CodexProvider

        self.register("claude_code", ClaudeCodeProvider)
        self.register("codex_cli", CodexProvider)

    def register(self, name: str, provider_class: Type[ReviewProvider]) -> None:
        self._providers[name] = provider_class
        logger.debug(f"注册 Provider: {name}")

    def get_class(self, name: str) -> Optional[Type[ReviewProvider]]:
        return self._providers.get(name)

    def create(self, name: str, **kwargs: object) -> ReviewProvider:
        provider_class = self._providers.get(name)
        if not provider_class:
            available = list(self._providers.keys())
            raise ValueError(f"未知的 Provider: {name}，可用: {available}")
        return provider_class(**kwargs)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())
