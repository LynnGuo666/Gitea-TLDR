"""
审查引擎 —— Provider 统一调度入口
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .providers.base import ReviewProvider, ReviewResult
from .providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ReviewEngine:
    """统一审查入口，根据配置路由到对应 Provider"""

    def __init__(
        self,
        default_provider: str = "claude_code",
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

        self._default_provider = self.registry.create(
            default_provider, cli_path=cli_path, debug=debug
        )
        self.last_error: Optional[str] = None

    @property
    def provider(self) -> ReviewProvider:
        """处理提供方相关逻辑。

        Args:
            无。

        Returns:
            ReviewProvider 类型结果。
        """
        return self._default_provider

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

    async def analyze_pr_simple(
        self,
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
        """分析pr simple。

        Args:
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
        result = await provider.analyze_pr_simple(
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
        """处理提供方相关逻辑。

        Args:
            name: 名称标识。

        Returns:
            ReviewProvider 类型结果。
        """
        if name and name != self.default_provider_name:
            cli_path = self._cli_paths.get(name, name)
            return self.registry.create(name, cli_path=cli_path, debug=self.debug)
        return self._default_provider
