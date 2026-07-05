"""drop namespace table and audit dead fields

删除零业务写入的 Namespace 表、两个 FK 列（repositories.namespace_id、
provider_credentials.namespace_id）、AuditEvent.namespace_id 列，以及
AuditEvent 中从未写入实际值的 changed_fields_json / sensitive_fields_json。

SQLite 下 batch_alter_table 会重建整张表，drop_column 自动消除附带 FK。

Revision ID: 0002
Revises: f3a7b1c8d2e4
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "f3a7b1c8d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def _has_column(table: str, column: str) -> bool:
        return column in {c["name"] for c in inspector.get_columns(table)}

    # 1. 删除 repositories.namespace_id（batch 重建表时 FK 自动消除）
    with op.batch_alter_table("repositories") as batch:
        if _has_column("repositories", "namespace_id"):
            batch.drop_column("namespace_id")

    # 2. 删除 provider_credentials.namespace_id
    with op.batch_alter_table("provider_credentials") as batch:
        if _has_column("provider_credentials", "namespace_id"):
            batch.drop_column("namespace_id")

    # 3. 删除 audit_events.namespace_id + 两个死字段
    with op.batch_alter_table("audit_events") as batch:
        if _has_column("audit_events", "namespace_id"):
            batch.drop_column("namespace_id")
        if _has_column("audit_events", "changed_fields_json"):
            batch.drop_column("changed_fields_json")
        if _has_column("audit_events", "sensitive_fields_json"):
            batch.drop_column("sensitive_fields_json")

    # 4. 删除 namespaces 表
    if inspector.has_table("namespaces"):
        op.drop_table("namespaces")

    logger.info("已删除 Namespace 表、3 个 FK 列、AuditEvent 2 个死字段")


def downgrade() -> None:
    # 1. 重建 namespaces 表
    op.create_table(
        "namespaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider", "name", name="uq_namespaces_provider_name"),
    )

    # 2. 重建 repositories.namespace_id（带 FK）
    with op.batch_alter_table("repositories") as batch:
        batch.add_column(sa.Column("namespace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_repositories_namespace_id",
            "namespaces",
            ["namespace_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 3. 重建 provider_credentials.namespace_id（带 FK）
    with op.batch_alter_table("provider_credentials") as batch:
        batch.add_column(sa.Column("namespace_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_provider_credentials_namespace_id",
            "namespaces",
            ["namespace_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 4. 重建 audit_events.namespace_id + 两个字段（无 FK）
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("namespace_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("changed_fields_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("sensitive_fields_json", sa.Text(), nullable=True))

    logger.info("已回滚：重建 Namespace 表、3 个 FK 列、AuditEvent 2 个字段")
