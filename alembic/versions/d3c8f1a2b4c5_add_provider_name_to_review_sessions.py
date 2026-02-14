from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3c8f1a2b4c5"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("review_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("provider_name", sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("review_sessions") as batch_op:
        batch_op.drop_column("provider_name")
