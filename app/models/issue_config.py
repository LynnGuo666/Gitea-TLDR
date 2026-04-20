"""
Issue 分析配置模型（独立于 PR 审查的 ModelConfig）
"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import encryption_service

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .repository import Repository


DEFAULT_ISSUE_FOCUS = ["bug", "duplicate", "design"]


class IssueConfig(Base, TimestampMixin):
    """Issue 分析引擎配置表。

    仓库级与全局级共用同一张表：
    - repository_id 为 NULL 且 is_default=True 时表示全局默认配置；
    - repository_id 非 NULL 时表示仓库特化配置。
    """

    __tablename__ = "issue_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    config_name: Mapped[str] = mapped_column(String(100), nullable=False)
    engine: Mapped[str] = mapped_column(String(100), default="forge", nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    api_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    _api_key: Mapped[Optional[str]] = mapped_column(
        "api_key", Text, nullable=True, comment="Provider Auth Token（加密存储）"
    )
    wire_api: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default=None
    )
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_focus: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON数组: ['bug', 'duplicate', 'design', 'performance', 'question']",
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    repository: Mapped[Optional["Repository"]] = relationship(
        "Repository", back_populates="issue_config"
    )

    @property
    def api_key(self) -> Optional[str]:
        if not self._api_key:
            return None
        return encryption_service.decrypt(self._api_key)

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self._api_key = encryption_service.encrypt(value) if value else value

    def get_focus(self) -> List[str]:
        import json

        if not self.default_focus:
            return list(DEFAULT_ISSUE_FOCUS)
        try:
            data = json.loads(self.default_focus)
            if isinstance(data, list):
                return [str(item) for item in data if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return list(DEFAULT_ISSUE_FOCUS)

    def set_focus(self, focus: List[str]) -> None:
        import json

        self.default_focus = json.dumps(list(focus))
