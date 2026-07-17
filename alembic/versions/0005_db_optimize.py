"""db optimize

捡回 v2.3.0 里与 tag_review 无关的纯优化（被 revert 连累），并补齐高频
排序/过滤列的索引、删除冗余单列索引与死列。全部用 `_has_column`/`_has_index`
幂等检查，让环境 X（从未升级到 v2.3.0，需新增）和环境 Y（曾升级又 revert，
已有则跳过）都能收敛到一致状态。

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-17 00:00:00.000000
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.runtime.migration")


def _has_column(inspector, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(inspector, table: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table))


# 新增索引清单：(index_name, table, columns)
NEW_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_analysis_runs_started_at", "analysis_runs", ["started_at"]),
    ("ix_analysis_runs_completed_at", "analysis_runs", ["completed_at"]),
    (
        "ix_analysis_runs_repository_kind_number",
        "analysis_runs",
        ["repository_id", "kind", "external_number", "head_sha"],
    ),
    ("ix_webhook_events_created_at", "webhook_events", ["created_at"]),
    ("ix_audit_events_created_at", "audit_events", ["created_at"]),
    ("ix_provider_runs_started_at", "provider_runs", ["started_at"]),
]

# 冗余单列索引：已有 UQ (provider,owner,name) 覆盖，删除。
REDUNDANT_INDEXES: list[tuple[str, str]] = [
    ("ix_repositories_owner", "repositories"),
    ("ix_repositories_name", "repositories"),
    ("ix_repositories_full_name", "repositories"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. 新增高频排序/过滤索引（batch_alter_table 重建表时 SQLite 会丢失
    #    已有索引，因此统一在表重建之后用 create_index 显式补齐）。
    for name, table, cols in NEW_INDEXES:
        if not _has_index(inspector, table, name):
            try:
                op.create_index(name, table, cols)
            except Exception as exc:  # noqa: BLE001 - 幂等保护
                logger.warning("创建索引 %s 失败（跳过）: %s", name, exc)

    # 2. 删除 repositories 冗余单列索引（UQ (provider,owner,name) 已覆盖）
    for name, table in REDUNDANT_INDEXES:
        if _has_index(inspector, table, name):
            try:
                op.drop_index(name, table_name=table)
            except Exception as exc:  # noqa: BLE001
                logger.warning("删除索引 %s 失败（跳过）: %s", name, exc)

    # 3. 删除 usage_events.provider_run_id 死列（永远 NULL）
    with op.batch_alter_table("usage_events") as batch:
        if _has_column(inspector, "usage_events", "provider_run_id"):
            batch.drop_column("provider_run_id")

    logger.info("已补齐索引、删除冗余索引与 usage_events.provider_run_id 死列")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. 恢复 usage_events.provider_run_id 死列（nullable，恢复结构对称）
    with op.batch_alter_table("usage_events") as batch:
        if not _has_column(inspector, "usage_events", "provider_run_id"):
            batch.add_column(sa.Column("provider_run_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_usage_events_provider_run_id",
                "provider_runs",
                ["provider_run_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # 2. 恢复 repositories 冗余单列索引
    for name, col in (
        ("ix_repositories_owner", "owner"),
        ("ix_repositories_name", "name"),
        ("ix_repositories_full_name", "full_name"),
    ):
        if not _has_index(inspector, "repositories", name):
            try:
                op.create_index(name, "repositories", [col])
            except Exception as exc:  # noqa: BLE001
                logger.warning("恢复索引 %s 失败（跳过）: %s", name, exc)

    # 3. 删除新增索引
    for name, table, _cols in NEW_INDEXES:  # noqa: B007
        if _has_index(inspector, table, name):
            try:
                op.drop_index(name, table_name=table)
            except Exception as exc:  # noqa: BLE001
                logger.warning("删除索引 %s 失败（跳过）: %s", name, exc)

    logger.info("已回滚：恢复 provider_run_id 列、冗余索引，删除新增索引")
