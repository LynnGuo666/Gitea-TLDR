"""
仓库模型
"""
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import encryption_service

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .model_config import ModelConfig
    from .review_session import ReviewSession


class Repository(Base, TimestampMixin):
    """仓库表"""
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("owner", "repo_name", name="uq_owner_repo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # 内部存储加密后的 webhook secret
    _webhook_secret: Mapped[Optional[str]] = mapped_column(
        "webhook_secret", Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 关系
    model_config: Mapped[Optional["ModelConfig"]] = relationship(
        "ModelConfig",
        back_populates="repository",
        uselist=False,
        cascade="all, delete-orphan"
    )
    review_sessions: Mapped[List["ReviewSession"]] = relationship(
        "ReviewSession",
        back_populates="repository",
        cascade="all, delete-orphan"
    )

    @property
    def webhook_secret(self) -> Optional[str]:
        """获取 Webhook Secret（自动解密）"""
        if not self._webhook_secret:
            return None
        return encryption_service.decrypt(self._webhook_secret)

    @webhook_secret.setter
    def webhook_secret(self, value: Optional[str]) -> None:
        """设置 Webhook Secret（自动加密）"""
        self._webhook_secret = encryption_service.encrypt(value) if value else value

    @property
    def full_name(self) -> str:
        """获取仓库全名"""
        return f"{self.owner}/{self.repo_name}"
