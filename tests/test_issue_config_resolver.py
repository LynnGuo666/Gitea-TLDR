from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.issue_config import DEFAULT_ISSUE_FOCUS, IssueConfig
from app.services.issue_config_resolver import (
    clear_issue_provider_overrides,
    has_explicit_issue_override,
    has_non_provider_issue_settings,
    resolve_issue_config,
)


def _build_config(**kwargs) -> IssueConfig:
    cfg = IssueConfig(
        config_name=kwargs.pop("config_name", "cfg"),
        engine=kwargs.pop("engine", "forge"),
    )
    # plain attribute assignment is enough for resolver tests; we skip the SQLAlchemy
    # descriptors that require a session.
    cfg.api_url = kwargs.pop("api_url", None)
    cfg.model = kwargs.pop("model", None)
    cfg.wire_api = kwargs.pop("wire_api", None)
    cfg.temperature = kwargs.pop("temperature", None)
    cfg.max_tokens = kwargs.pop("max_tokens", None)
    cfg.custom_prompt = kwargs.pop("custom_prompt", None)
    cfg.is_default = kwargs.pop("is_default", False)
    cfg._api_key = kwargs.pop("encrypted_api_key", None)
    focus = kwargs.pop("focus", None)
    if focus is not None:
        cfg.set_focus(focus)
    else:
        cfg.default_focus = None
    assert not kwargs, f"未消费参数: {kwargs}"
    return cfg


def test_resolver_returns_default_when_both_empty():
    resolved = resolve_issue_config(None, None)

    assert resolved.inherit_global is True
    assert resolved.engine == "forge"
    assert resolved.api_url is None
    assert resolved.api_key is None
    assert resolved.default_focus == list(DEFAULT_ISSUE_FOCUS)


def test_resolver_falls_back_to_global_when_repo_missing():
    global_cfg = _build_config(
        engine="forge",
        api_url="https://api.example.com",
        model="claude-sonnet-4",
        focus=["bug", "design"],
    )

    resolved = resolve_issue_config(None, global_cfg)

    assert resolved.inherit_global is True
    assert resolved.api_url == "https://api.example.com"
    assert resolved.model == "claude-sonnet-4"
    assert resolved.default_focus == ["bug", "design"]


def test_resolver_respects_explicit_repo_override():
    global_cfg = _build_config(api_url="https://global", model="model-a")
    repo_cfg = _build_config(api_url="https://repo", model="model-b", focus=["bug"])

    resolved = resolve_issue_config(repo_cfg, global_cfg)

    assert resolved.inherit_global is False
    assert resolved.api_url == "https://repo"
    assert resolved.model == "model-b"
    assert resolved.default_focus == ["bug"]


def test_clear_issue_overrides_keeps_non_provider_settings():
    cfg = _build_config(api_url="https://repo", model="model-b", focus=["bug"])
    assert has_explicit_issue_override(cfg) is True
    clear_issue_provider_overrides(cfg)

    assert cfg.api_url is None
    assert cfg.model is None
    assert cfg.engine == "forge"
    assert has_non_provider_issue_settings(cfg) is True


def test_has_explicit_issue_override_false_when_only_focus():
    cfg = _build_config(focus=["bug"])
    assert has_explicit_issue_override(cfg) is False
