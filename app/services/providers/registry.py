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
        """初始化实例状态。

        Args:
            无。

        Returns:
            无返回值。
        """
        self._providers: Dict[str, Type[ReviewProvider]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """处理builtins相关逻辑。

        Args:
            无。

        Returns:
            无返回值。
        """
        from .claude_code import ClaudeCodeProvider
        from .codex_cli import CodexProvider
        from .forge.provider import ForgeProvider

        self.register("claude_code", ClaudeCodeProvider)
        self.register("codex_cli", CodexProvider)
        self.register("forge", ForgeProvider)

    def register(self, name: str, provider_class: Type[ReviewProvider]) -> None:
        """注册相关内容。

        Args:
            name: 名称标识。
            provider_class: 提供方实现类。

        Returns:
            无返回值。
        """
        self._providers[name] = provider_class
        logger.debug(f"注册 Provider: {name}")

    def get_class(self, name: str) -> Optional[Type[ReviewProvider]]:
        """获取class。

        Args:
            name: 名称标识。

        Returns:
            可能为空的结果。
        """
        return self._providers.get(name)

    def create(self, name: str, **kwargs: object) -> ReviewProvider:
        """创建相关内容。

        Args:
            name: 名称标识。
            **kwargs: 传递给提供方构造函数的附加参数。

        Returns:
            ReviewProvider 类型结果。
        """
        provider_class = self._providers.get(name)
        if not provider_class:
            available = list(self._providers.keys())
            raise ValueError(f"未知的 Provider: {name}，可用: {available}")
        return provider_class(**kwargs)

    def list_providers(self) -> List[str]:
        """列出提供方列表。

        Args:
            无。

        Returns:
            列表结果。
        """
        return list(self._providers.keys())
