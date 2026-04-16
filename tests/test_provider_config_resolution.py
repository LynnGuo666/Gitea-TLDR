from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models import ModelConfig
from app.services.provider_config_resolver import (
    clear_provider_overrides,
    has_explicit_provider_override,
    has_non_provider_settings,
    resolve_provider_config,
)


def test_resolve_provider_config_keeps_global_model_when_repo_only_has_review_settings():
    repo_config = ModelConfig(
        repository_id=1,
        config_name="repo",
        engine="claude_code",
    )
    repo_config.set_focus(["security"])

    global_config = ModelConfig(
        repository_id=None,
        config_name="global",
        engine="forge",
        model="claude-sonnet-4-20250514",
        api_url="https://api.example.com",
    )

    resolved = resolve_provider_config(
        repo_config,
        global_config,
        default_engine="claude_code",
    )

    assert resolved.inherit_global is True
    assert resolved.engine == "forge"
    assert resolved.model == "claude-sonnet-4-20250514"
    assert resolved.api_url == "https://api.example.com"


def test_has_explicit_provider_override_detects_non_default_engine():
    repo_config = ModelConfig(
        repository_id=1,
        config_name="repo",
        engine="codex_cli",
    )

    assert has_explicit_provider_override(repo_config) is True


def test_clear_provider_overrides_preserves_review_settings():
    repo_config = ModelConfig(
        repository_id=1,
        config_name="repo",
        engine="forge",
        model="claude-test",
        api_url="https://repo.example.com",
        wire_api="responses",
    )
    repo_config.set_focus(["logic"])
    repo_config.set_features(["comment", "review"])

    clear_provider_overrides(repo_config)

    assert repo_config.engine == "claude_code"
    assert repo_config.model is None
    assert repo_config.api_url is None
    assert repo_config.api_key is None
    assert repo_config.wire_api is None
    assert has_non_provider_settings(repo_config) is True
    assert repo_config.get_focus() == ["logic"]
    assert repo_config.get_features() == ["comment", "review"]
