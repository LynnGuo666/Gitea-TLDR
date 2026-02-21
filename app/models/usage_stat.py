"""
使用量统计模型
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .repository import Repository
    from .review_session import ReviewSession
    from .user import User


class UsageStat(Base):
    """使用量统计表"""

    __tablename__ = "usage_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # 统计日期
    stat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Token估算
    estimated_input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    estimated_output_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # API调用统计
    gitea_api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clone_operations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # 关系
    repository: Mapped["Repository"] = relationship("Repository")
    review_session: Mapped[Optional["ReviewSession"]] = relationship(
        "ReviewSession", back_populates="usage_stat"
    )
    user: Mapped[Optional["User"]] = relationship("User")
