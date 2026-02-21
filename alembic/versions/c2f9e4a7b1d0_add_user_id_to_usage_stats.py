"""add user id to usage stats

Revision ID: c2f9e4a7b1d0
Revises: b8d4e2f06c1a
Create Date: 2026-02-21 09:40:00.000000

"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f9e4a7b1d0"
down_revision: Union[str, None] = "b8d4e2f06c1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_usage_stats_user_id", ["user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_usage_stats_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    conn = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("username", sa.String()),
        sa.column("email", sa.String()),
        sa.column("role", sa.String()),
        sa.column("permissions", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("last_login_at", sa.DateTime()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    usage_table = sa.table(
        "usage_stats",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.Integer()),
    )

    target_user_id = 1
    id1_exists = conn.execute(
        sa.select(users_table.c.id).where(users_table.c.id == target_user_id).limit(1)
    ).scalar_one_or_none()

    if id1_exists is None:
        username_for_id1 = "user1"
        username_conflict = conn.execute(
            sa.select(users_table.c.id)
            .where(users_table.c.username == username_for_id1)
            .limit(1)
        ).scalar_one_or_none()
        if username_conflict is not None:
            username_for_id1 = "user-id-1"

        now = datetime.utcnow()
        conn.execute(
            sa.insert(users_table).values(
                id=target_user_id,
                username=username_for_id1,
                email=None,
                role="user",
                permissions=None,
                is_active=True,
                last_login_at=None,
                created_at=now,
                updated_at=now,
            )
        )

    conn.execute(
        sa.update(usage_table)
        .where(usage_table.c.user_id.is_(None))
        .values(user_id=target_user_id)
    )


def downgrade() -> None:
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.drop_constraint("fk_usage_stats_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_usage_stats_user_id")
        batch_op.drop_column("user_id")
