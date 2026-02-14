"""
审查会话模型
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .inline_comment import InlineComment
    from .repository import Repository
    from .usage_stat import UsageStat


class ReviewSession(Base):
    """审查会话记录表"""

    __tablename__ = "review_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # PR信息
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pr_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pr_author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    head_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    base_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    head_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 触发信息
    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="auto / manual"
    )
    engine: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="审查引擎名称，如 claude_code / codex_cli"
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="实际使用的模型标识"
    )
    config_source: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="header / repo_config / global_default"
    )
    enabled_features: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON数组"
    )
    focus_areas: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON数组"
    )

    # 分析信息
    analysis_mode: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="full / simple"
    )
    diff_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 结果信息
    overall_severity: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="critical / high / medium / low / info"
    )
    summary_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inline_comments_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    overall_success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间信息
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 关系
    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="review_sessions"
    )
    inline_comments: Mapped[List["InlineComment"]] = relationship(
        "InlineComment", back_populates="review_session", cascade="all, delete-orphan"
    )
    usage_stat: Mapped[Optional["UsageStat"]] = relationship(
        "UsageStat",
        back_populates="review_session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def get_features(self) -> List[str]:
        """获取功能列表"""
        import json

        if not self.enabled_features:
            return []
        try:
            return json.loads(self.enabled_features)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_focus(self) -> List[str]:
        """获取审查重点列表"""
        import json

        if not self.focus_areas:
            return []
        try:
            return json.loads(self.focus_areas)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_features(self, features: List[str]) -> None:
        """设置功能列表"""
        import json

        self.enabled_features = json.dumps(features)

    def set_focus(self, focus: List[str]) -> None:
        """设置审查重点列表"""
        import json

        self.focus_areas = json.dumps(focus)
