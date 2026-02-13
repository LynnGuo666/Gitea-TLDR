"""
API Key 池模型
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class KeyRotationStrategy(str, Enum):
    """Key 轮换策略"""

    ROUND_ROBIN = "round_robin"  # 轮询
    LEAST_USED = "least_used"  # 最少使用
    WEIGHTED = "weighted"  # 权重
    PRIORITY = "priority"  # 优先级


class ApiKey(Base, TimestampMixin):
    """API Key 池表"""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key_alias: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True, comment="Key 别名"
    )
    provider_api_base_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Provider API Base URL"
    )
    provider_auth_token: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Provider Auth Token（加密存储）"
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="优先级（数字越大优先级越高）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
    daily_quota: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="每日配额（Token数）"
    )
    monthly_quota: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="每月配额（Token数）"
    )

    # 统计字段
    total_calls: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="总调用次数"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="总Token消耗"
    )
    today_calls: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="今日调用次数"
    )
    today_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="今日Token消耗"
    )
    month_calls: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="本月调用次数"
    )
    month_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="本月Token消耗"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, comment="最后使用时间"
    )

    @property
    def quota_remaining_daily(self) -> Optional[int]:
        """今日剩余配额"""
        if self.daily_quota is None:
            return None
        return max(0, self.daily_quota - self.today_tokens)

    @property
    def quota_remaining_monthly(self) -> Optional[int]:
        """本月剩余配额"""
        if self.monthly_quota is None:
            return None
        return max(0, self.monthly_quota - self.month_tokens)

    @property
    def quota_usage_percent(self) -> Optional[float]:
        """配额使用百分比（优先使用月配额）"""
        if self.monthly_quota:
            return (self.month_tokens / self.monthly_quota) * 100
        elif self.daily_quota:
            return (self.today_tokens / self.daily_quota) * 100
        return None

    @property
    def is_quota_exceeded(self) -> bool:
        """是否超出配额"""
        if self.daily_quota and self.today_tokens >= self.daily_quota:
            return True
        if self.monthly_quota and self.month_tokens >= self.monthly_quota:
            return True
        return False
