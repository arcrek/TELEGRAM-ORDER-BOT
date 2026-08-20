"""add app_settings table

Revision ID: g7b8c9d0e1f2
Revises: c1d2e3f4a5b6
Create Date: 2026-06-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "g7b8c9d0e1f2"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "app_settings" not in tables:
        op.create_table(
            "app_settings",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column(
                "timezone",
                sa.String(),
                nullable=False,
                server_default="Asia/Ho_Chi_Minh",
            ),
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

    if "app_settings" in tables:
        op.drop_table("app_settings")
