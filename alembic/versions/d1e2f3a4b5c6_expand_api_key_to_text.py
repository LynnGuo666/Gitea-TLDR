"""expand api_key to Text in model_configs

Revision ID: d1e2f3a4b5c6
Revises: b7e3a1f09d42
Create Date: 2026-03-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "b7e3a1f09d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.alter_column(
            "api_key",
            existing_type=sa.String(500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.alter_column(
            "api_key",
            existing_type=sa.Text(),
            type_=sa.String(500),
            existing_nullable=True,
        )
