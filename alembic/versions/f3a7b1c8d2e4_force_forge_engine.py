"""force forge engine

一次性数据迁移：把 repository_configs.engine 中的 legacy CLI engine
（`claude_code`、`codex_cli`）以及空值统一切换为 `forge`，并清空 wire_api。

Forge 现在是唯一默认且推荐的引擎；CLI provider 已迁至 `extras/`，
仅在 `ENABLE_LEGACY_PROVIDERS=true` 时按需注册。

downgrade 选择 no-op：将历史值还原会重新引入失效 CLI engine，
而 ReviewEngine 已经具备退回 forge 的兜底逻辑，无需 downgrade。

Revision ID: f3a7b1c8d2e4
Revises: e1f2a3b4c5d6
Create Date: 2026-05-25 12:00:00.000000
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f3a7b1c8d2e4"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "UPDATE repository_configs "
            "SET engine = 'forge', wire_api = NULL "
            "WHERE engine IN ('claude_code', 'codex_cli') "
            "   OR engine IS NULL OR engine = ''"
        )
    )

    rowcount = getattr(result, "rowcount", None)
    if rowcount is None:
        logger.info("force_forge_engine: 已执行更新（无法读取受影响行数）")
    else:
        logger.info(
            "force_forge_engine: 已将 %d 条 repository_configs 切换到 forge",
            rowcount,
        )


def downgrade() -> None:
    # 历史 engine 值不再合法，不做任何还原。
    pass
