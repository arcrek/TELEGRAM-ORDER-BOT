"""add iotd settings table

Revision ID: 9b0c1d2e3f4a
Revises: 8f9a0b1c2d3e
Create Date: 2026-01-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b0c1d2e3f4a"
down_revision = "8f9a0b1c2d3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "iotd_settings" not in tables:
        op.create_table(
            "iotd_settings",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("image_url", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "iotd_settings" in tables:
        op.drop_table("iotd_settings")

