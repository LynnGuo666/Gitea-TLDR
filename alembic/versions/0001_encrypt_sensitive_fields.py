"""加密所有敏感字段

Revision ID: 0001
Revises: d1e2f3a4b5c6
Create Date: 2026-03-20 00:00:00.000000

"""
import base64
import binascii
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def _looks_encrypted(value: str) -> bool:
    """判断字段值是否已经是加密密文（有效 base64 且长度符合 SealedBox 最小密文长度）。

    SealedBox 的密文至少包含 32 字节的临时公钥 + Poly1305 MAC（16 字节），
    即明文为 0 时密文至少 48 字节，base64 后至少 64 字符。
    """
    if not value or len(value) < 64:
        return False
    try:
        decoded = base64.b64decode(value.encode("ascii"))
        return len(decoded) >= 48
    except (binascii.Error, ValueError):
        return False


def _encrypt_plaintext(value: str) -> str:
    """使用全局 encryption_service 加密明文。"""
    from app.core.encryption import encryption_service

    return encryption_service.encrypt(value)


def upgrade() -> None:
    """加密各表中尚未加密的敏感字段存量数据。

    策略：逐行检查，若字段值不像加密密文（base64 长度不足 SealedBox 最小值），
    则视为旧明文，加密后回写。已加密的行跳过，保持幂等性。
    """
    bind = op.get_bind()

    # --- model_configs.api_key ---
    rows = bind.execute(
        sa.text("SELECT id, api_key FROM model_configs WHERE api_key IS NOT NULL")
    ).fetchall()
    for row_id, api_key in rows:
        if not _looks_encrypted(api_key):
            try:
                bind.execute(
                    sa.text("UPDATE model_configs SET api_key = :val WHERE id = :id"),
                    {"val": _encrypt_plaintext(api_key), "id": row_id},
                )
                logger.info("model_configs id=%s api_key 已加密", row_id)
            except Exception as exc:
                logger.error("model_configs id=%s api_key 加密失败: %s", row_id, exc)

    # --- api_keys.provider_auth_token ---
    rows = bind.execute(
        sa.text(
            "SELECT id, provider_auth_token FROM api_keys"
            " WHERE provider_auth_token IS NOT NULL"
        )
    ).fetchall()
    for row_id, token in rows:
        if not _looks_encrypted(token):
            try:
                bind.execute(
                    sa.text(
                        "UPDATE api_keys SET provider_auth_token = :val WHERE id = :id"
                    ),
                    {"val": _encrypt_plaintext(token), "id": row_id},
                )
                logger.info("api_keys id=%s provider_auth_token 已加密", row_id)
            except Exception as exc:
                logger.error(
                    "api_keys id=%s provider_auth_token 加密失败: %s", row_id, exc
                )

    # --- repositories.webhook_secret ---
    rows = bind.execute(
        sa.text(
            "SELECT id, webhook_secret FROM repositories"
            " WHERE webhook_secret IS NOT NULL"
        )
    ).fetchall()
    for row_id, secret in rows:
        if not _looks_encrypted(secret):
            try:
                bind.execute(
                    sa.text(
                        "UPDATE repositories SET webhook_secret = :val WHERE id = :id"
                    ),
                    {"val": _encrypt_plaintext(secret), "id": row_id},
                )
                logger.info("repositories id=%s webhook_secret 已加密", row_id)
            except Exception as exc:
                logger.error(
                    "repositories id=%s webhook_secret 加密失败: %s", row_id, exc
                )

    # --- user_sessions.access_token / refresh_token ---
    rows = bind.execute(
        sa.text(
            "SELECT session_id, access_token, refresh_token FROM user_sessions"
        )
    ).fetchall()
    for session_id, access_token, refresh_token in rows:
        updates: dict = {}
        if access_token and not _looks_encrypted(access_token):
            try:
                updates["access_token"] = _encrypt_plaintext(access_token)
            except Exception as exc:
                logger.error(
                    "user_sessions %s access_token 加密失败: %s", session_id, exc
                )
        if refresh_token and not _looks_encrypted(refresh_token):
            try:
                updates["refresh_token"] = _encrypt_plaintext(refresh_token)
            except Exception as exc:
                logger.error(
                    "user_sessions %s refresh_token 加密失败: %s", session_id, exc
                )
        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["session_id"] = session_id
            bind.execute(
                sa.text(
                    f"UPDATE user_sessions SET {set_clause}"  # noqa: S608
                    " WHERE session_id = :session_id"
                ),
                updates,
            )
            logger.info("user_sessions %s 敏感字段已加密", session_id)


def downgrade() -> None:
    # 加密数据无法还原为原始明文，此降级仅作占位
    # 若需回滚，请从备份恢复数据库
    pass
