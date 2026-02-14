"""add wire_api to model_configs

Revision ID: b7e3a1f09d42
Revises: cf5892f17789
Create Date: 2026-02-15 13:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e3a1f09d42"
down_revision: Union[str, None] = "cf5892f17789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "wire_api",
                sa.String(50),
                nullable=True,
                server_default="responses",
                comment="Codex wire API type: responses | chat-completions",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.drop_column("wire_api")
