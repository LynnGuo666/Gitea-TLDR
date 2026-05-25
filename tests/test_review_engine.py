"""ReviewEngine 解析与 fallback 行为测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.review.engine import ReviewEngine
from app.review.providers.base import ReviewProvider


class _StubProvider(ReviewProvider):
    """最小可注册 provider，用于驱动 ReviewEngine 解析路径。"""

    PROVIDER_NAME = "stub"

    def __init__(self, cli_path: str = "stub", debug: bool = False) -> None:
        self.cli_path = cli_path
        self.debug = debug

    @property
    def name(self) -> str:
        return self.PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return "Stub"

    async def analyze_pr(self, *args, **kwargs):  # type: ignore[override]
        return None


class _BrokenProvider(_StubProvider):
    PROVIDER_NAME = "broken"

    def __init__(self, cli_path: str = "broken", debug: bool = False) -> None:
        raise RuntimeError("CLI 未安装")


def test_default_provider_lazy_loaded() -> None:
    """构造时不应触发 default provider 的实例化。"""

    engine = ReviewEngine(default_provider="forge", cli_path="claude", debug=False)
    # 默认 provider 还未懒加载
    assert "forge" not in engine._provider_cache


def test_resolve_forge_returns_registered_provider() -> None:
    engine = ReviewEngine(default_provider="forge", cli_path="claude", debug=False)
    provider = engine._resolve_provider("forge")
    assert provider.name == "forge"


def test_unknown_engine_falls_back_to_forge_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """传入未注册的 engine 时退回到 forge 并打日志。"""

    engine = ReviewEngine(default_provider="forge", cli_path="claude", debug=False)
    with caplog.at_level("WARNING"):
        provider = engine._resolve_provider("claude_code")
    assert provider.name == "forge"
    assert any("退回到 forge" in record.message for record in caplog.records)


def test_resolve_without_forge_raises_for_unknown_engine() -> None:
    """没有 forge 且 engine 未注册时，应抛 ValueError 而不是静默失败。"""

    engine = ReviewEngine(default_provider="absent", cli_path="x", debug=False)
    engine.registry._providers.pop("forge", None)
    with pytest.raises(ValueError, match="未知的 Provider"):
        engine._resolve_provider("absent")


def test_construction_exception_falls_back_to_forge(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """如果构造目标 provider 抛异常，应退回 forge 并记录日志。"""

    engine = ReviewEngine(default_provider="forge", cli_path="claude", debug=False)
    engine.registry.register("broken", _BrokenProvider)
    with caplog.at_level("WARNING"):
        provider = engine._resolve_provider("broken")
    assert provider.name == "forge"
    assert any("退回到 forge provider" in record.message for record in caplog.records)


def test_default_provider_property_uses_lazy_resolver() -> None:
    """`engine.provider` 应通过 `_resolve_provider` 走懒加载路径。"""

    engine = ReviewEngine(default_provider="forge", cli_path="claude", debug=False)
    assert engine.provider.name == "forge"
    # 第二次访问命中缓存
    assert engine.provider.name == "forge"
    assert "forge" in engine._provider_cache
