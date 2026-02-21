from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True, comment="Gitea 用户名"
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
        comment="角色: user / admin / super_admin",
    )
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def has_permission(self, resource: str, action: str) -> bool:
        if self.role == "super_admin":
            return True

        if not self.permissions:
            return action in ["read"]

        import json

        try:
            perms = json.loads(self.permissions)
            return action in perms.get(resource, [])
        except (json.JSONDecodeError, TypeError):
            return False

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"
