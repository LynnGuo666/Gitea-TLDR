"""drop tag review columns

清理 v2.3.0 引入的 tag 区间审查遗留列：`analysis_runs.from_tag` / `to_tag`。
tag_review 功能已在 4f3e23e 永久移除，相关迁移文件（原 0003）也已随 revert 删除。

本迁移的关键作用是收敛环境差异：
- 环境 X（从未升级到 v2.3.0）：`alembic_version=0002`，无 from_tag/to_tag 列 → upgrade 时跳过。
- 环境 Y（曾升级到 v2.3.0 又 revert）：`alembic_version=0003`，有 from_tag/to_tag 列。
  但 0003 迁移文件已删除，`alembic upgrade head` 会报
  `Can't locate revision identified by '0003'` 直接启动失败。
  entrypoint 会自动 `alembic stamp 0002` 后重试，本迁移负责物理 drop 这两列。

注意 revision id 必须是 `0004`，不能复用 `0003`——复用会让环境 Y 误以为已在 head
而跳过清理。

Revision ID: 0004
Revises: 0002
Create Date: 2026-07-17 00:00:00.000000
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def _has_column(table: str, column: str) -> bool:
        return column in {c["name"] for c in inspector.get_columns(table)}

    # drop from_tag / to_tag（仅环境 Y 会实际 drop，环境 X 跳过）
    with op.batch_alter_table("analysis_runs") as batch:
        if _has_column("analysis_runs", "from_tag"):
            batch.drop_column("from_tag")
        if _has_column("analysis_runs", "to_tag"):
            batch.drop_column("to_tag")

    logger.info("已清理 analysis_runs.from_tag / to_tag（tag_review 功能已永久移除）")


def downgrade() -> None:
    # no-op：tag_review 功能已永久移除，不还原 from_tag / to_tag 列。
    # 回退到 0002 后再 upgrade 会再次进入本迁移，upgrade 是幂等的，无需在 downgrade 重建列。
    logger.info("0004 downgrade 为 no-op：tag_review 功能已永久移除，不还原 from_tag/to_tag")
