"""rename columns to clear names and add model column

Revision ID: f1a2b3c4d5e6
Revises: b7e3a1f09d42
Create Date: 2026-02-15 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "b7e3a1f09d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.alter_column("model_name", new_column_name="engine")
        batch_op.alter_column("provider_api_base_url", new_column_name="api_url")
        batch_op.alter_column("provider_auth_token", new_column_name="api_key")
        batch_op.add_column(
            sa.Column(
                "model",
                sa.String(200),
                nullable=True,
                comment="Actual LLM model identifier",
            )
        )

    with op.batch_alter_table("review_sessions") as batch_op:
        batch_op.alter_column("provider_name", new_column_name="engine")
        batch_op.alter_column("model_name", new_column_name="model")


def downgrade() -> None:
    with op.batch_alter_table("review_sessions") as batch_op:
        batch_op.alter_column("model", new_column_name="model_name")
        batch_op.alter_column("engine", new_column_name="provider_name")

    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.drop_column("model")
        batch_op.alter_column("api_key", new_column_name="provider_auth_token")
        batch_op.alter_column("api_url", new_column_name="provider_api_base_url")
        batch_op.alter_column("engine", new_column_name="model_name")
