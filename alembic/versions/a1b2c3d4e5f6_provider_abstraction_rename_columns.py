"""provider abstraction rename columns

Revision ID: a1b2c3d4e5f6
Revises: c65ea449dfc3
Create Date: 2026-02-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c65ea449dfc3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # model_configs: anthropic_base_url → provider_api_base_url,
    #                anthropic_auth_token → provider_auth_token
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.alter_column(
            "anthropic_base_url", new_column_name="provider_api_base_url"
        )
        batch_op.alter_column(
            "anthropic_auth_token", new_column_name="provider_auth_token"
        )

    # api_keys: same renames
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.alter_column(
            "anthropic_base_url", new_column_name="provider_api_base_url"
        )
        batch_op.alter_column(
            "anthropic_auth_token", new_column_name="provider_auth_token"
        )

    # usage_stats: claude_api_calls → provider_api_calls
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.alter_column("claude_api_calls", new_column_name="provider_api_calls")

    # Data migration: model_name "claude" → "claude_code"
    op.execute(
        "UPDATE model_configs SET model_name = 'claude_code' "
        "WHERE model_name = 'claude'"
    )


def downgrade() -> None:
    # Reverse data migration
    op.execute(
        "UPDATE model_configs SET model_name = 'claude' "
        "WHERE model_name = 'claude_code'"
    )

    # usage_stats: provider_api_calls → claude_api_calls
    with op.batch_alter_table("usage_stats") as batch_op:
        batch_op.alter_column("provider_api_calls", new_column_name="claude_api_calls")

    # api_keys: reverse renames
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.alter_column(
            "provider_auth_token", new_column_name="anthropic_auth_token"
        )
        batch_op.alter_column(
            "provider_api_base_url", new_column_name="anthropic_base_url"
        )

    # model_configs: reverse renames
    with op.batch_alter_table("model_configs") as batch_op:
        batch_op.alter_column(
            "provider_auth_token", new_column_name="anthropic_auth_token"
        )
        batch_op.alter_column(
            "provider_api_base_url", new_column_name="anthropic_base_url"
        )
