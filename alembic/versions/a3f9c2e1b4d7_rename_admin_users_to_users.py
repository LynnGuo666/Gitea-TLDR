"""rename admin_users to users

Revision ID: a3f9c2e1b4d7
Revises: f1a2b3c4d5e6
Create Date: 2026-02-21 07:40:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "a3f9c2e1b4d7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("admin_users", "users")
    # 重建索引（SQLite 不支持 rename index，先 drop 再 create）
    op.drop_index("ix_admin_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="admin_users")
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)
    op.rename_table("users", "admin_users")
