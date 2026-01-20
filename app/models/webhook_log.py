"""
Webhook 日志模型
"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class WebhookLog(Base, TimestampMixin):
    """Webhook 日志表"""

    __tablename__ = "webhook_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="请求ID（用于追踪）",
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="仓库ID",
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="事件类型（pull_request/issue_comment）",
    )
    payload: Mapped[str] = mapped_column(
        Text, nullable=False, comment="完整的Webhook Payload（JSON格式）"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="处理状态：success/error/retrying",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )
    processing_time_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="处理耗时（毫秒）"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="重试次数"
    )

    @property
    def is_success(self) -> bool:
        """是否成功"""
        return self.status == "success"

    @property
    def is_failed(self) -> bool:
        """是否失败"""
        return self.status == "error"

    @property
    def is_retrying(self) -> bool:
        """是否重试中"""
        return self.status == "retrying"
