"""Issue 分析配置解析辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.models import DEFAULT_ISSUE_FOCUS, IssueConfig

DEFAULT_ISSUE_ENGINE = "forge"


@dataclass
class ResolvedIssueConfig:
    inherit_global: bool
    engine: str
    model: Optional[str]
    api_url: Optional[str]
    api_key: Optional[str]
    wire_api: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    custom_prompt: Optional[str]
    default_focus: List[str] = field(default_factory=lambda: list(DEFAULT_ISSUE_FOCUS))


def has_explicit_issue_override(config: Optional[IssueConfig]) -> bool:
    """判断仓库级 Issue 配置是否真的显式覆盖了 Provider 设置。"""
    if config is None:
        return False
    if config.api_url or config.api_key or config.model or config.wire_api:
        return True
    engine = (config.engine or "").strip()
    if engine and engine != DEFAULT_ISSUE_ENGINE:
        return True
    return False


def has_non_provider_issue_settings(config: Optional[IssueConfig]) -> bool:
    """判断 focus/custom_prompt 等非 Provider 字段是否还承载。"""
    if config is None:
        return False
    return any(
        [
            config.temperature is not None,
            config.max_tokens is not None,
            bool((config.custom_prompt or "").strip()),
            bool(config.default_focus),
        ]
    )


def clear_issue_provider_overrides(config: IssueConfig) -> None:
    """清空仓库级 Issue Provider 覆盖，但保留 focus/custom_prompt。"""
    config.api_url = None
    config.api_key = None
    config.model = None
    config.wire_api = None
    config.engine = DEFAULT_ISSUE_ENGINE


def resolve_issue_config(
    repo_config: Optional[IssueConfig],
    global_config: Optional[IssueConfig],
    *,
    default_engine: str = DEFAULT_ISSUE_ENGINE,
) -> ResolvedIssueConfig:
    """按"仓库显式覆盖 > 全局 > 默认值"解析实际 Issue 配置。"""

    def _focus_of(config: Optional[IssueConfig]) -> Optional[List[str]]:
        if not config or not config.default_focus:
            return None
        focus = config.get_focus()
        return focus or None

    if has_explicit_issue_override(repo_config):
        focus = _focus_of(repo_config) or _focus_of(global_config) or list(
            DEFAULT_ISSUE_FOCUS
        )
        assert repo_config is not None
        return ResolvedIssueConfig(
            inherit_global=False,
            engine=(repo_config.engine or default_engine),
            model=repo_config.model,
            api_url=(
                repo_config.api_url
                or (global_config.api_url if global_config else None)
            ),
            api_key=(
                repo_config.api_key
                or (global_config.api_key if global_config else None)
            ),
            wire_api=(
                repo_config.wire_api
                or (global_config.wire_api if global_config else None)
            ),
            temperature=(
                repo_config.temperature
                if repo_config.temperature is not None
                else (global_config.temperature if global_config else None)
            ),
            max_tokens=(
                repo_config.max_tokens
                if repo_config.max_tokens is not None
                else (global_config.max_tokens if global_config else None)
            ),
            custom_prompt=(
                repo_config.custom_prompt
                or (global_config.custom_prompt if global_config else None)
            ),
            default_focus=focus,
        )

    if global_config is not None:
        focus = _focus_of(global_config) or list(DEFAULT_ISSUE_FOCUS)
        return ResolvedIssueConfig(
            inherit_global=True,
            engine=(global_config.engine or default_engine),
            model=global_config.model,
            api_url=global_config.api_url,
            api_key=global_config.api_key,
            wire_api=global_config.wire_api,
            temperature=global_config.temperature,
            max_tokens=global_config.max_tokens,
            custom_prompt=global_config.custom_prompt,
            default_focus=focus,
        )

    return ResolvedIssueConfig(
        inherit_global=True,
        engine=default_engine,
        model=None,
        api_url=None,
        api_key=None,
        wire_api=None,
        temperature=None,
        max_tokens=None,
        custom_prompt=None,
        default_focus=list(DEFAULT_ISSUE_FOCUS),
    )
