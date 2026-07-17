"""
审查引擎 —— Provider 统一调度入口
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .providers.base import ReviewProvider, ReviewResult
from .providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)

_FORGE_FALLBACK = "forge"


class ReviewEngine:
    """统一审查入口，根据配置路由到对应 Provider"""

    def __init__(
        self,
        default_provider: str = "forge",
        cli_path: str = "claude",
        debug: bool = False,
        provider_cli_paths: Optional[Dict[str, str]] = None,
    ):
        """初始化实例状态。

        Args:
            default_provider: 默认审查提供方名称。
            cli_path: CLI 可执行文件路径。
            debug: 是否启用调试模式。
            provider_cli_paths: 提供方到 CLI 路径的映射。

        Returns:
            无返回值。
        """
        self.registry = ProviderRegistry()
        self.default_provider_name = default_provider
        self.debug = debug
        self._cli_paths: Dict[str, str] = provider_cli_paths or {}
        self._cli_paths.setdefault(default_provider, cli_path)

        self._provider_cache: Dict[str, ReviewProvider] = {}
        self.last_error: Optional[str] = None

    @property
    def provider(self) -> ReviewProvider:
        """获取默认 provider（懒加载）。"""
        return self._resolve_provider(self.default_provider_name)

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        engine: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: Optional[str] = None,
        wire_api: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        """分析pr。

        Args:
            repo_path: 本地仓库路径。
            diff_content: PR 的差异内容。
            focus_areas: 审查关注点列表。
            pr_info: PR 基本信息。
            api_url: API 地址。
            api_key: API 密钥。
            engine: 审查引擎名称。
            custom_prompt: 自定义提示词。
            model: 模型名称。
            wire_api: 底层 API 协议标识。

        Returns:
            可能为空的结果。
        """
        provider = self._resolve_provider(engine)
        self.last_error = None
        result = await provider.analyze_pr(
            repo_path,
            diff_content,
            focus_areas,
            pr_info,
            api_url=api_url,
            api_key=api_key,
            custom_prompt=custom_prompt,
            model=model,
            wire_api=wire_api,
        )
        if result is None:
            self.last_error = provider.last_error
        return result

    def _resolve_provider(self, name: Optional[str] = None) -> ReviewProvider:
        """按名称解析 provider，未命中时退回到 forge（若可用）。

        懒加载：默认 provider 仅在首次使用时构造，避免应用启动阶段因 CLI 缺失而失败。

        Args:
            name: 名称标识。

        Returns:
            ReviewProvider 实例。
        """
        target = name or self.default_provider_name
        available = self.registry.list_providers()

        if target not in available:
            if _FORGE_FALLBACK in available and target != _FORGE_FALLBACK:
                logger.warning(
                    "engine %s 未注册（可用: %s），退回到 forge",
                    target,
                    available,
                )
                target = _FORGE_FALLBACK
            else:
                raise ValueError(f"未知的 Provider: {target}，可用: {available}")

        if target in self._provider_cache:
            logger.debug("使用 provider: %s (缓存)", target)
            return self._provider_cache[target]

        cli_path = self._cli_paths.get(target, target)
        try:
            provider = self.registry.create(target, cli_path=cli_path, debug=self.debug)
        except Exception as exc:
            logger.exception("构造 provider %s 失败: %s", target, exc)
            if target != _FORGE_FALLBACK and _FORGE_FALLBACK in available:
                logger.warning("退回到 forge provider")
                return self._resolve_provider(_FORGE_FALLBACK)
            raise

        self._provider_cache[target] = provider
        logger.debug("使用 provider: %s", target)
        return provider
