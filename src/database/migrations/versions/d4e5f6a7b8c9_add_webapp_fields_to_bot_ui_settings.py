"""add webapp fields to bot_ui_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-04 00:00:00.000000

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
    tables = inspector.get_table_names()

    if "bot_ui_settings" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("bot_ui_settings")}

    if "webapp_button_text" not in columns:
        op.add_column("bot_ui_settings", sa.Column("webapp_button_text", sa.Text(), nullable=True))
    if "webapp_url" not in columns:
        op.add_column("bot_ui_settings", sa.Column("webapp_url", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "bot_ui_settings" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("bot_ui_settings")}

    if "webapp_url" in columns:
        op.drop_column("bot_ui_settings", "webapp_url")
    if "webapp_button_text" in columns:
        op.drop_column("bot_ui_settings", "webapp_button_text")

