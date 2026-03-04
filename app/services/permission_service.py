"""用户权限检查服务"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)


def has_permission(user: "User", resource: str, action: str) -> bool:
    """
    检查用户是否拥有指定资源的操作权限。

    Args:
        user: 用户 ORM 实体
        resource: 资源名称（如 "repos"、"users"）
        action: 操作名称（如 "read"、"write"）

    Returns:
        True 表示有权限，False 表示无权限
    """
    if user.role == "super_admin":
        return True

    if not user.permissions:
        return action in ["read"]

    try:
        perms = json.loads(user.permissions)
        return action in perms.get(resource, [])
    except (json.JSONDecodeError, TypeError):
        logger.warning("用户 %s 的 permissions 字段格式无效", user.username)
        return False
