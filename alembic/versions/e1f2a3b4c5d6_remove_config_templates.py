"""remove config_templates table and template columns from repository_configs

Revision ID: e1f2a3b4c5d6
Revises: d2c4b6a8e9f0
Create Date: 2026-05-11 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d2c4b6a8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅在 repository_configs 确实还带这两个列时才尝试删除。
    # 当本迁移在全新库上运行（d2c4b6a8e9f0 已用当前 schema 建表，
    # 这两列本就不存在）时，batch_alter_table 的 drop_column 会抛
    # KeyError，因此先做存在性判断。
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("repository_configs")}
    with op.batch_alter_table("repository_configs") as batch_op:
        if "source_template_id" in existing_cols:
            batch_op.drop_column("source_template_id")
        if "template_version_copied_at" in existing_cols:
            batch_op.drop_column("template_version_copied_at")

    if inspector.has_table("config_templates"):
        op.drop_table("config_templates")


def downgrade() -> None:
    op.create_table(
        "config_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope_type", sa.String(50), nullable=False),
        sa.Column("scope_key", sa.String(100), nullable=False),
        sa.Column("namespace_id", sa.Integer(), nullable=True),
        sa.Column("scenario", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("engine", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("credential_id", sa.Integer(), nullable=True),
        sa.Column("wire_api", sa.String(50), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("custom_prompt", sa.Text(), nullable=True),
        sa.Column("focus_json", sa.Text(), nullable=True),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by_actor_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_key", "scenario", "name", name="uq_config_templates_scope_scenario"
        ),
    )

    with op.batch_alter_table("repository_configs") as batch_op:
        batch_op.add_column(
            sa.Column("source_template_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("template_version_copied_at", sa.DateTime(), nullable=True)
        )
