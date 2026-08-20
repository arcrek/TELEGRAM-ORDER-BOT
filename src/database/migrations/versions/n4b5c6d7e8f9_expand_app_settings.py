"""Expand global app settings with operator identity fields."""

import sqlalchemy as sa
from alembic import op

revision = "n4b5c6d7e8f9"
down_revision = "m3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "system_name",
            sa.String(length=80),
            nullable=False,
            server_default="Bot Order System",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("bot_url", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "support_line_1", sa.String(length=200), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "support_line_2", sa.String(length=200), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "order_prefix", sa.String(length=8), nullable=False, server_default="ORD"
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "api_docs_url", sa.String(length=2048), nullable=False, server_default=""
        ),
    )


def downgrade() -> None:
    for name in (
        "api_docs_url",
        "order_prefix",
        "support_line_2",
        "support_line_1",
        "bot_url",
        "system_name",
    ):
        op.drop_column("app_settings", name)
