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
        self.registry = ProviderRegistry()
        self.default_provider_name = default_provider
        self.debug = debug
        self._cli_paths: Dict[str, str] = provider_cli_paths or {}
        self._cli_paths.setdefault(default_provider, cli_path)

        self._default_provider = self.registry.create(
            default_provider, cli_path=cli_path, debug=debug
        )

    @property
    def provider(self) -> ReviewProvider:
        return self._default_provider

    async def analyze_pr(
        self,
        repo_path: Path,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        provider_api_base_url: Optional[str] = None,
        provider_auth_token: Optional[str] = None,
        provider_name: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        provider = self._resolve_provider(provider_name)
        return await provider.analyze_pr(
            repo_path,
            diff_content,
            focus_areas,
            pr_info,
            provider_api_base_url=provider_api_base_url,
            provider_auth_token=provider_auth_token,
            custom_prompt=custom_prompt,
        )

    async def analyze_pr_simple(
        self,
        diff_content: str,
        focus_areas: List[str],
        pr_info: dict,
        provider_api_base_url: Optional[str] = None,
        provider_auth_token: Optional[str] = None,
        provider_name: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> Optional[ReviewResult]:
        provider = self._resolve_provider(provider_name)
        return await provider.analyze_pr_simple(
            diff_content,
            focus_areas,
            pr_info,
            provider_api_base_url=provider_api_base_url,
            provider_auth_token=provider_auth_token,
            custom_prompt=custom_prompt,
        )

    def _resolve_provider(self, name: Optional[str] = None) -> ReviewProvider:
        if name and name != self.default_provider_name:
            cli_path = self._cli_paths.get(name, name)
            return self.registry.create(name, cli_path=cli_path, debug=self.debug)
        return self._default_provider
