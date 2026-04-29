"""ForgeSession — Forge agentic loop 运行记录"""

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .issue_session import IssueSession
    from .repository import Repository
    from .review_session import ReviewSession


def _generate_session_id() -> str:
    return "fgs-" + secrets.token_hex(8)


class ForgeSession(Base):
    """Forge agentic loop 运行记录表"""

    __tablename__ = "forge_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    scenario: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="running")

    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    review_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("review_sessions.id", ondelete="SET NULL"), nullable=True
    )
    issue_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("issue_sessions.id", ondelete="SET NULL"), nullable=True
    )

    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0)

    messages_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    repository: Mapped[Optional["Repository"]] = relationship("Repository")
    review_session: Mapped[Optional["ReviewSession"]] = relationship("ReviewSession")
    issue_session: Mapped[Optional["IssueSession"]] = relationship("IssueSession")

    def get_messages(self) -> List[Dict[str, Any]]:
        """解析 messages_json 为列表。"""
        import json

        if not self.messages_json:
            return []
        try:
            result = json.loads(self.messages_json)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
