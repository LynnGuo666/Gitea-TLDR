"""运行时可热更新的行为配置缓存。

启动时由 seed() 从 DB 加载（DB 无值则以 config.py 默认值写入），
之后通过 get() 同步读取、update() 同步写入（前端 PUT /settings 后调用）。
"""

import json
from typing import Any

from app.core.config import settings

# key → (category, description, default_value)
RUNTIME_KEYS: dict[str, tuple[str, str, Any]] = {
    "default_provider": (
        "review",
        "默认审查引擎（claude_code / codex_cli）",
        settings.default_provider,
    ),
    "default_review_focus": (
        "review",
        "默认审查重点，JSON 数组，如 [\"quality\",\"security\"]",
        settings.default_review_focus,
    ),
    "auto_request_reviewer": (
        "review",
        "完成审查后是否自动将 bot 设为审查者",
        settings.auto_request_reviewer,
    ),
    "bot_username": (
        "review",
        "Bot 用户名，用于识别 @ 提及和自动请求审查者",
        settings.bot_username,
    ),
    "claude_usage_proxy_enabled": (
        "provider",
        "是否启用 Claude usage 捕获代理",
        settings.claude_usage_proxy_enabled,
    ),
    "claude_usage_proxy_debug": (
        "provider",
        "是否输出 Claude usage 代理诊断日志",
        settings.claude_usage_proxy_debug,
    ),
    "webhook_log_retention_days": (
        "admin",
        "成功 Webhook 日志保留天数",
        settings.webhook_log_retention_days,
    ),
    "webhook_log_retention_days_failed": (
        "admin",
        "失败 Webhook 日志保留天数",
        settings.webhook_log_retention_days_failed,
    ),
}

_cache: dict[str, Any] = {}


async def seed(session: Any) -> None:
    """启动时调用：将缺失字段写入 DB，然后从 DB 加载所有值进缓存。"""
    from app.services.admin_service import AdminService

    svc = AdminService(session)
    for key, (category, description, default) in RUNTIME_KEYS.items():
        row = await svc.get_setting(key)
        if row is None:
            row = await svc.set_setting(key, default, category, description)
        _cache[key] = json.loads(row.value)
    await session.commit()


def get(key: str, fallback: Any = None) -> Any:
    """同步读缓存，缓存未命中时返回 fallback。"""
    return _cache.get(key, fallback)


def update(key: str, value: Any) -> None:
    """前端写入 DB 后同步更新缓存（仅限 RUNTIME_KEYS 中的字段）。"""
    if key in RUNTIME_KEYS:
        _cache[key] = value
