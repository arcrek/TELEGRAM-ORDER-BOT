"""Fix benefit_mode default to 'both'

Rows added by the previous migration got server_default='bonus', which prevents
discount tiers from being evaluated even when configured. Change the default to
'both' so that configured tiers apply automatically unless the admin explicitly
restricts the mode.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-22 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Change column server_default for new rows
    # (SQLite doesn't support ALTER COLUMN, so we handle both dialects)
    dialect = conn.dialect.name
    if dialect != "sqlite":
        op.alter_column(
            "product_variations",
            "benefit_mode",
            server_default="both",
            existing_type=sa.String(),
            existing_nullable=False,
        )

    # Migrate existing 'bonus' rows to 'both' — these were set by the prior
    # migration's server_default, not by an intentional admin choice.
    conn.execute(
        sa.text(
            "UPDATE product_variations SET benefit_mode = 'both' WHERE benefit_mode = 'bonus'"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()

    dialect = conn.dialect.name
    if dialect != "sqlite":
        op.alter_column(
            "product_variations",
            "benefit_mode",
            server_default="bonus",
            existing_type=sa.String(),
            existing_nullable=False,
        )

    conn.execute(
        sa.text(
            "UPDATE product_variations SET benefit_mode = 'bonus' WHERE benefit_mode = 'both'"
        )
    )
