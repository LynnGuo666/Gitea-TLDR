"""
AI模型配置
"""
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .repository import Repository


class ModelConfig(Base, TimestampMixin):
    """AI模型配置表"""
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    config_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="claude", nullable=False)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_features: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON数组: ['comment', 'review', 'status']"
    )
    default_focus: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON数组: ['quality', 'security', 'performance', 'logic']"
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Anthropic API 配置（仓库级别）
    anthropic_base_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Anthropic API Base URL"
    )
    anthropic_auth_token: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Anthropic Auth Token"
    )

    # 关系
    repository: Mapped[Optional["Repository"]] = relationship(
        "Repository",
        back_populates="model_config"
    )

    def get_features(self) -> List[str]:
        """获取功能列表"""
        import json
        if not self.default_features:
            return ["comment"]
        try:
            return json.loads(self.default_features)
        except (json.JSONDecodeError, TypeError):
            return ["comment"]

    def get_focus(self) -> List[str]:
        """获取审查重点列表"""
        import json
        if not self.default_focus:
            return ["quality", "security", "performance", "logic"]
        try:
            return json.loads(self.default_focus)
        except (json.JSONDecodeError, TypeError):
            return ["quality", "security", "performance", "logic"]

    def set_features(self, features: List[str]) -> None:
        """设置功能列表"""
        import json
        self.default_features = json.dumps(features)

    def set_focus(self, focus: List[str]) -> None:
        """设置审查重点列表"""
        import json
        self.default_focus = json.dumps(focus)
