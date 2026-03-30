from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.encryption import encryption_service

from .base import Base, TimestampMixin


class UserSession(Base, TimestampMixin):
    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    _access_token: Mapped[str] = mapped_column("access_token", Text, nullable=False)
    _refresh_token: Mapped[Optional[str]] = mapped_column(
        "refresh_token", Text, nullable=True
    )
    scope: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    user_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @property
    def access_token(self) -> str:
        """获取访问令牌（自动解密）"""
        return encryption_service.decrypt(self._access_token)

    @access_token.setter
    def access_token(self, value: str) -> None:
        """设置访问令牌（自动加密）"""
        self._access_token = encryption_service.encrypt(value) if value else value

    @property
    def refresh_token(self) -> Optional[str]:
        """获取刷新令牌（自动解密）"""
        if not self._refresh_token:
            return None
        return encryption_service.decrypt(self._refresh_token)

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]) -> None:
        """设置刷新令牌（自动加密）"""
        self._refresh_token = encryption_service.encrypt(value) if value else value
