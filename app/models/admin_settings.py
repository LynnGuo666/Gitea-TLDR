"""
全局配置模型
"""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AdminSettings(Base, TimestampMixin):
    """全局配置表"""

    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True, comment="配置键"
    )
    value: Mapped[str] = mapped_column(
        Text, nullable=False, comment="配置值（JSON格式）"
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="配置分类：claude/review/performance/advanced",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="配置说明"
    )

    @property
    def key_display(self) -> str:
        """显示名称"""
        return self.key.replace("_", " ").title()
