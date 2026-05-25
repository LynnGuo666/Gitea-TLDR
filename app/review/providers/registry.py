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
        """初始化实例状态。"""
        self._providers: Dict[str, Type[ReviewProvider]] = {}
        self._register_builtins()
        self._maybe_register_extras()

    def _register_builtins(self) -> None:
        """注册始终启用的内置 provider（Forge）。"""
        from .forge.provider import ForgeProvider

        self.register("forge", ForgeProvider)

    def _maybe_register_extras(self) -> None:
        """按 `settings.enable_legacy_providers` 注册 legacy CLI providers。

        默认关闭。导入失败仅记录 warning，不影响 Forge 主链路。
        """
        try:
            from app.core import settings
        except Exception as exc:  # pragma: no cover - 配置加载异常时跳过
            logger.warning("加载 settings 失败，跳过 legacy providers: %s", exc)
            return

        if not getattr(settings, "enable_legacy_providers", False):
            return

        try:
            from .extras.claude_code import ClaudeCodeProvider

            self.register("claude_code", ClaudeCodeProvider)
        except Exception as exc:
            logger.warning("注册 legacy claude_code provider 失败: %s", exc)

        try:
            from .extras.codex_cli import CodexProvider

            self.register("codex_cli", CodexProvider)
        except Exception as exc:
            logger.warning("注册 legacy codex_cli provider 失败: %s", exc)

    def register(self, name: str, provider_class: Type[ReviewProvider]) -> None:
        """注册 provider 实现。"""
        self._providers[name] = provider_class
        logger.debug("注册 Provider: %s", name)

    def get_class(self, name: str) -> Optional[Type[ReviewProvider]]:
        """根据名称查找 provider 类。"""
        return self._providers.get(name)

    def create(self, name: str, **kwargs: object) -> ReviewProvider:
        """构造 provider 实例。"""
        provider_class = self._providers.get(name)
        if not provider_class:
            available = list(self._providers.keys())
            raise ValueError(f"未知的 Provider: {name}，可用: {available}")
        return provider_class(**kwargs)

    def list_providers(self) -> List[str]:
        """已注册 provider 名称列表。"""
        return list(self._providers.keys())

    def list_issue_providers(self) -> List[str]:
        """列出支持 Issue 分析的提供方。"""
        supported: List[str] = []
        for name, provider_class in self._providers.items():
            try:
                provider = provider_class()
            except Exception:  # pragma: no cover - 安全兜底
                continue
            if getattr(provider, "supports_issue", lambda: False)():
                supported.append(name)
        return supported
