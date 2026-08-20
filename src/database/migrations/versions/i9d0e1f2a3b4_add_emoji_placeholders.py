"""add emoji_placeholders table + notification header/footer placeholder ids

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-06-22 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "i9d0e1f2a3b4"
down_revision = "h8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "emoji_placeholders" not in tables:
        op.create_table(
            "emoji_placeholders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=True),
            sa.Column("set_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    ns_cols = [c["name"] for c in inspector.get_columns("notification_settings")]
    if "header_placeholder_id" not in ns_cols:
        op.add_column("notification_settings", sa.Column("header_placeholder_id", sa.Integer(), nullable=True))
    if "footer_placeholder_id" not in ns_cols:
        op.add_column("notification_settings", sa.Column("footer_placeholder_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    ns_cols = [c["name"] for c in inspector.get_columns("notification_settings")]
    if "footer_placeholder_id" in ns_cols:
        op.drop_column("notification_settings", "footer_placeholder_id")
    if "header_placeholder_id" in ns_cols:
        op.drop_column("notification_settings", "header_placeholder_id")

    if "emoji_placeholders" in inspector.get_table_names():
        op.drop_table("emoji_placeholders")
