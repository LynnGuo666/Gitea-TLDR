"""
管理员用户模型
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AdminUser(Base, TimestampMixin):
    """管理员用户表"""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True, comment="Gitea 用户名"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="用户邮箱"
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="admin",
        comment="角色: super_admin 或 admin",
    )
    permissions: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="权限配置（JSON格式）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, comment="最后登录时间"
    )

    def has_permission(self, resource: str, action: str) -> bool:
        """
        检查是否有指定权限

        Args:
            resource: 资源名称（如 "repos", "config", "users"）
            action: 操作类型（如 "read", "write", "delete"）

        Returns:
            是否有权限
        """
        # super_admin 拥有所有权限
        if self.role == "super_admin":
            return True

        # admin 根据 permissions 字段判断
        if not self.permissions:
            # 默认 admin 权限
            return action in ["read"]

        import json

        try:
            perms = json.loads(self.permissions)
            return action in perms.get(resource, [])
        except (json.JSONDecodeError, TypeError):
            return False

    @property
    def is_super_admin(self) -> bool:
        """是否为超级管理员"""
        return self.role == "super_admin"
