from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.provider_config_resolver import (
    clear_provider_overrides,
    has_explicit_provider_override,
    has_non_provider_settings,
    resolve_provider_config,
)


@dataclass
class ProviderConfigStub:
    repository_id: Optional[int]
    engine: str
    model: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    wire_api: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    custom_prompt: Optional[str] = None
    _focus: list[str] = field(default_factory=list)
    _features: list[str] = field(default_factory=list)

    @property
    def default_focus(self) -> list[str]:
        return self._focus

    @property
    def default_features(self) -> list[str]:
        return self._features

    def set_focus(self, focus: list[str]) -> None:
        self._focus = focus

    def get_focus(self) -> list[str]:
        return self._focus

    def set_features(self, features: list[str]) -> None:
        self._features = features

    def get_features(self) -> list[str]:
        return self._features


def test_resolve_provider_config_keeps_global_model_when_repo_only_has_review_settings():
    repo_config = ProviderConfigStub(
        repository_id=1,
        engine="claude_code",
    )
    repo_config.set_focus(["security"])

    global_config = ProviderConfigStub(
        repository_id=None,
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
    repo_config = ProviderConfigStub(
        repository_id=1,
        engine="codex_cli",
    )

    assert has_explicit_provider_override(repo_config) is True


def test_clear_provider_overrides_preserves_review_settings():
    repo_config = ProviderConfigStub(
        repository_id=1,
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
