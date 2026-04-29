"""add forge_sessions table

Revision ID: b9e4f1a2c3d5
Revises: a7c53d2f108b
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9e4f1a2c3d5"
down_revision: Union[str, None] = "a7c53d2f108b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forge_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("scenario", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("review_session_id", sa.Integer(), nullable=True),
        sa.Column("issue_session_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_calls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_json", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_creation_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["review_session_id"], ["review_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["issue_session_id"], ["issue_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_forge_sessions_session_id"),
        "forge_sessions",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_forge_sessions_repository_id"),
        "forge_sessions",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_forge_sessions_repository_id"), table_name="forge_sessions")
    op.drop_index(op.f("ix_forge_sessions_session_id"), table_name="forge_sessions")
    op.drop_table("forge_sessions")
