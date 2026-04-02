"""add cache tokens to usage stats

Revision ID: e3a1b2c4d5f6
Revises: 0001
Create Date: 2026-04-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3a1b2c4d5f6"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.add_column(
            sa.Column(
                "cache_creation_input_tokens",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "cache_read_input_tokens",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.drop_column("cache_read_input_tokens")
        batch_op.drop_column("cache_creation_input_tokens")
