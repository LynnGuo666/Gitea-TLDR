"""add review audit fields

Revision ID: cf5892f17789
Revises: a1b2c3d4e5f6
Create Date: 2026-02-14 11:40:10.334849

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cf5892f17789"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("review_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "provider_name",
                sa.String(50),
                nullable=True,
                comment="claude_code / codex_cli",
            )
        )
        batch_op.add_column(
            sa.Column(
                "model_name",
                sa.String(100),
                nullable=True,
                comment="Actual model identifier",
            )
        )
        batch_op.add_column(
            sa.Column(
                "config_source",
                sa.String(20),
                nullable=True,
                comment="header / repo_config / global_default",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("review_sessions") as batch_op:
        batch_op.drop_column("config_source")
        batch_op.drop_column("model_name")
        batch_op.drop_column("provider_name")
