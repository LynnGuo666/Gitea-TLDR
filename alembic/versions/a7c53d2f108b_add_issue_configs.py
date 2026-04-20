"""add issue configs table

Revision ID: a7c53d2f108b
Revises: 4f2a6d1c9b8e
Create Date: 2026-04-19 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c53d2f108b"
down_revision: Union[str, None] = "4f2a6d1c9b8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "issue_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("config_name", sa.String(length=100), nullable=False),
        sa.Column("engine", sa.String(length=100), nullable=False, server_default="forge"),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("api_url", sa.String(length=500), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("wire_api", sa.String(length=50), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("custom_prompt", sa.Text(), nullable=True),
        sa.Column("default_focus", sa.Text(), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", name="uq_issue_configs_repository_id"),
    )
    op.create_index(
        op.f("ix_issue_configs_repository_id"),
        "issue_configs",
        ["repository_id"],
        unique=False,
    )

    with op.batch_alter_table("issue_sessions") as batch_op:
        batch_op.alter_column(
            "started_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "completed_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("issue_sessions") as batch_op:
        batch_op.alter_column(
            "completed_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    op.drop_index(op.f("ix_issue_configs_repository_id"), table_name="issue_configs")
    op.drop_table("issue_configs")
