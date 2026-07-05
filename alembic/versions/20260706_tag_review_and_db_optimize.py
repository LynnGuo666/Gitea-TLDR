"""tag review columns and db optimization

一次迁移完成三件事：
1. analysis_runs 新增 from_tag / to_tag 列（tag 区间审查）；
2. 补齐高频排序/过滤列索引、新增复合索引优化 get_review_run_by_head；
3. 删除冗余单列索引（repositories owner/name/full_name）与死列
   usage_events.provider_run_id（永远 NULL）。

SQLite 下 batch_alter_table 会重建整张表，drop_column 自动消除附带 FK。

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.runtime.migration")


def _has_column(inspector, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(inspector, table: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. analysis_runs 新增 from_tag / to_tag
    with op.batch_alter_table("analysis_runs") as batch:
        if not _has_column(inspector, "analysis_runs", "from_tag"):
            batch.add_column(sa.Column("from_tag", sa.String(255), nullable=True))
        if not _has_column(inspector, "analysis_runs", "to_tag"):
            batch.add_column(sa.Column("to_tag", sa.String(255), nullable=True))

    # 2. 新增索引（高频排序/过滤）。batch_alter_table 重建表时 SQLite 会
    #    丢失已有索引，因此统一在表重建之后用 create_index 显式补齐。
    new_indexes = [
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
    for name, table, cols in new_indexes:
        if not _has_index(inspector, table, name):
            try:
                op.create_index(name, table, cols)
            except Exception as exc:  # noqa: BLE001 - 幂等保护
                logger.warning("创建索引 %s 失败（跳过）: %s", name, exc)

    # 3. 删除 repositories 冗余单列索引（保留 UQ (provider,owner,name) 即可）
    for name in ("ix_repositories_owner", "ix_repositories_name", "ix_repositories_full_name"):
        if _has_index(inspector, "repositories", name):
            try:
                op.drop_index(name, table_name="repositories")
            except Exception as exc:  # noqa: BLE001
                logger.warning("删除索引 %s 失败（跳过）: %s", name, exc)

    # 4. 删除 usage_events.provider_run_id 死列
    with op.batch_alter_table("usage_events") as batch:
        if _has_column(inspector, "usage_events", "provider_run_id"):
            batch.drop_column("provider_run_id")

    logger.info("已新增 from_tag/to_tag 列、补齐索引、删除冗余索引与 provider_run_id 列")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. 恢复 usage_events.provider_run_id
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

    # 2. 恢复 repositories 单列索引
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
    for name, table in [
        ("ix_analysis_runs_started_at", "analysis_runs"),
        ("ix_analysis_runs_completed_at", "analysis_runs"),
        ("ix_analysis_runs_repository_kind_number", "analysis_runs"),
        ("ix_webhook_events_created_at", "webhook_events"),
        ("ix_audit_events_created_at", "audit_events"),
        ("ix_provider_runs_started_at", "provider_runs"),
    ]:
        if _has_index(inspector, table, name):
            try:
                op.drop_index(name, table_name=table)
            except Exception as exc:  # noqa: BLE001
                logger.warning("删除索引 %s 失败（跳过）: %s", name, exc)

    # 4. 删除 from_tag / to_tag
    with op.batch_alter_table("analysis_runs") as batch:
        if _has_column(inspector, "analysis_runs", "from_tag"):
            batch.drop_column("from_tag")
        if _has_column(inspector, "analysis_runs", "to_tag"):
            batch.drop_column("to_tag")

    logger.info("已回滚：恢复 provider_run_id 列、冗余索引，删除 from_tag/to_tag 与新索引")
