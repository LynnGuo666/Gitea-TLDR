"""
Issue 分析会话模型
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .repository import Repository
    from .usage_stat import UsageStat


class IssueSession(Base):
    """Issue 分析会话记录表"""

    __tablename__ = "issue_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    issue_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    issue_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    issue_author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issue_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="auto / manual"
    )
    engine: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Issue 分析引擎名称，当前固定为 forge"
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="实际使用的模型标识"
    )
    config_source: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="repo_config / global_default"
    )
    source_comment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bot_comment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    overall_severity: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="critical / high / medium / low / info"
    )
    summary_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_payload: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON 对象"
    )
    overall_success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="issue_sessions"
    )
    usage_stats: Mapped[List["UsageStat"]] = relationship(
        "UsageStat",
        back_populates="issue_session",
        cascade="all, delete-orphan",
    )

    def get_analysis_payload(self) -> Dict[str, Any]:
        """解析结构化分析结果。"""
        import json

        if not self.analysis_payload:
            return {}
        try:
            result = json.loads(self.analysis_payload)
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_analysis_payload(self, payload: Dict[str, Any]) -> None:
        """写入结构化分析结果。"""
        import json

        self.analysis_payload = json.dumps(payload, ensure_ascii=False)
