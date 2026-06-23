"""add emoji_thumbnails cache table

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-06-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "j0e1f2a3b4c5"
down_revision = "i9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "emoji_thumbnails" not in inspector.get_table_names():
        op.create_table(
            "emoji_thumbnails",
            sa.Column("custom_emoji_id", sa.String(), primary_key=True),
            sa.Column("data", sa.LargeBinary(), nullable=True),
            sa.Column("mime", sa.String(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "emoji_thumbnails" in inspector.get_table_names():
        op.drop_table("emoji_thumbnails")
