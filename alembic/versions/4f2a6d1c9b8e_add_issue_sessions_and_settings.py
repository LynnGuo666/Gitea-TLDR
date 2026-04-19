"""add issue sessions and repo issue settings

Revision ID: 4f2a6d1c9b8e
Revises: e3a1b2c4d5f6
Create Date: 2026-04-16 12:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f2a6d1c9b8e"
down_revision: Union[str, None] = "e3a1b2c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("repositories") as batch_op:
        batch_op.add_column(
            sa.Column("issue_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                "issue_auto_on_open",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "issue_manual_command_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )

    op.create_table(
        "issue_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("issue_title", sa.String(length=500), nullable=True),
        sa.Column("issue_author", sa.String(length=255), nullable=True),
        sa.Column("issue_state", sa.String(length=50), nullable=True),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("engine", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("config_source", sa.String(length=20), nullable=True),
        sa.Column("source_comment_id", sa.Integer(), nullable=True),
        sa.Column("bot_comment_id", sa.Integer(), nullable=True),
        sa.Column("overall_severity", sa.String(length=20), nullable=True),
        sa.Column("summary_markdown", sa.Text(), nullable=True),
        sa.Column("analysis_payload", sa.Text(), nullable=True),
        sa.Column("overall_success", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_issue_sessions_repository_id"), "issue_sessions", ["repository_id"], unique=False)
    op.create_index(op.f("ix_issue_sessions_issue_number"), "issue_sessions", ["issue_number"], unique=False)

    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.add_column(sa.Column("issue_session_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_usage_stats_issue_session_id"), ["issue_session_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_usage_stats_issue_session_id_issue_sessions",
            "issue_sessions",
            ["issue_session_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.drop_constraint("fk_usage_stats_issue_session_id_issue_sessions", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_usage_stats_issue_session_id"))
        batch_op.drop_column("issue_session_id")

    op.drop_index(op.f("ix_issue_sessions_issue_number"), table_name="issue_sessions")
    op.drop_index(op.f("ix_issue_sessions_repository_id"), table_name="issue_sessions")
    op.drop_table("issue_sessions")

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_column("issue_manual_command_enabled")
        batch_op.drop_column("issue_auto_on_open")
        batch_op.drop_column("issue_enabled")
