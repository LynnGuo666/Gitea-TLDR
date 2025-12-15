"""
行级评论模型
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .review_session import ReviewSession


class InlineComment(Base):
    """行级评论详情表"""
    __tablename__ = "inline_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_session_id: Mapped[int] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 位置信息
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    new_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    old_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 评论内容
    severity: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="critical / high / medium / low"
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # 关系
    review_session: Mapped["ReviewSession"] = relationship(
        "ReviewSession",
        back_populates="inline_comments"
    )
