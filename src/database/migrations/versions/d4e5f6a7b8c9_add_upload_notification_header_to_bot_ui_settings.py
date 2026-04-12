"""add upload_notification_header to bot_ui_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("bot_ui_settings")]

    if "upload_notification_header" not in columns:
        op.add_column(
            "bot_ui_settings",
            sa.Column("upload_notification_header", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("bot_ui_settings")]

    if "upload_notification_header" in columns:
        op.drop_column("bot_ui_settings", "upload_notification_header")
