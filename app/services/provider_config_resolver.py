"""Provider 配置解析辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models import ModelConfig

DEFAULT_PROVIDER_ENGINE = "claude_code"


@dataclass
class ResolvedProviderConfig:
    inherit_global: bool
    engine: str
    model: Optional[str]
    api_url: Optional[str]
    api_key: Optional[str]
    wire_api: Optional[str]


def has_explicit_provider_override(config: Optional[ModelConfig]) -> bool:
    """判断仓库级配置是否真的覆盖了 Provider 选择。"""
    if config is None:
        return False
    if config.api_url or config.api_key or config.model or config.wire_api:
        return True
    engine = (config.engine or "").strip()
    return bool(engine and engine != DEFAULT_PROVIDER_ENGINE)


def has_non_provider_settings(config: Optional[ModelConfig]) -> bool:
    """判断配置中是否还承载了 focus/features 等仓库级设置。"""
    if config is None:
        return False
    return any(
        [
            config.max_tokens is not None,
            config.temperature is not None,
            bool(config.custom_prompt),
            bool(config.default_features),
            bool(config.default_focus),
        ]
    )


def clear_provider_overrides(config: ModelConfig) -> None:
    """清空仓库级 Provider 覆盖，但保留 review settings。"""
    config.api_url = None
    config.api_key = None
    config.model = None
    config.wire_api = None
    config.engine = DEFAULT_PROVIDER_ENGINE


def resolve_provider_config(
    repo_config: Optional[ModelConfig],
    global_config: Optional[ModelConfig],
    *,
    default_engine: str,
) -> ResolvedProviderConfig:
    """按“仓库显式覆盖 > 全局 > 默认值”解析实际 Provider 配置。"""
    if has_explicit_provider_override(repo_config):
        return ResolvedProviderConfig(
            inherit_global=False,
            engine=(repo_config.engine or default_engine),
            model=repo_config.model,
            api_url=(repo_config.api_url or (global_config.api_url if global_config else None)),
            api_key=(repo_config.api_key or (global_config.api_key if global_config else None)),
            wire_api=(repo_config.wire_api or (global_config.wire_api if global_config else None)),
        )

    if global_config is not None:
        return ResolvedProviderConfig(
            inherit_global=True,
            engine=(global_config.engine or default_engine),
            model=global_config.model,
            api_url=global_config.api_url,
            api_key=global_config.api_key,
            wire_api=global_config.wire_api,
        )

    return ResolvedProviderConfig(
        inherit_global=True,
        engine=default_engine,
        model=None,
        api_url=None,
        api_key=None,
        wire_api=None,
    )
