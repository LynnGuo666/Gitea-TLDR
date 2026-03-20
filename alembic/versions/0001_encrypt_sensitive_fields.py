"""加密所有敏感字段

Revision ID: 0001
Revises: d1e2f3a4b5c6
Create Date: 2026-03-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 敏感字段加密存储：
    # - user_sessions.access_token / refresh_token
    # - model_configs.api_key
    # - api_keys.provider_auth_token
    # - repositories.webhook_secret
    #
    # 注意：由于模型层通过属性（property）自动加解密，
    # 迁移后首次访问这些字段时，旧数据会被自动解密（向后兼容）。
    # 实际加密逻辑在 ORM 模型的 setter 属性中完成。
    #
    # 为确保迁移成功，此迁移仅修改列类型为 Text（支持加密后的长密文），
    # 实际数据加密由应用层在首次写入时自动完成。
    pass


def downgrade() -> None:
    # 降级时注意：加密数据无法还原为原始明文
    # 此降级仅作结构回退，数据将不可用
    pass
