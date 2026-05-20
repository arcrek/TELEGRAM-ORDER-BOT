"""Add balance wallet system

Revision ID: 4d5966317fb6
Revises: 59e4eb17a8c1
Create Date: 2026-05-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d5966317fb6"
down_revision = "59e4eb17a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Add balance column to bot_users
    bot_user_columns = [c["name"] for c in inspector.get_columns("bot_users")]
    if "balance" not in bot_user_columns:
        op.add_column(
            "bot_users",
            sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        )

    # 2. Create topup_orders table
    if "topup_orders" not in existing_tables:
        op.create_table(
            "topup_orders",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("bot_user_id", sa.String(), nullable=False),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("payment_provider", sa.String(), nullable=True),
            sa.Column("payment_transaction_id", sa.String(), nullable=True),
            sa.Column("payment_message_ids", sa.Text(), nullable=True),
            sa.Column("payos_order_code", sa.BigInteger(), nullable=True),
            sa.Column("payos_payment_link_id", sa.String(), nullable=True),
            sa.Column("payos_checkout_url", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["bot_user_id"], ["bot_users.id"]),
            sa.UniqueConstraint("payos_order_code", name="uq_topup_orders_payos_order_code"),
        )

    # 3. Create balance_transactions table
    if "balance_transactions" not in existing_tables:
        op.create_table(
            "balance_transactions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("bot_user_id", sa.String(), nullable=False),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("balance_after", sa.BigInteger(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("reference_id", sa.String(), nullable=True),
            sa.Column("admin_id", sa.String(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["bot_user_id"], ["bot_users.id"]),
            sa.ForeignKeyConstraint(["admin_id"], ["admins.id"]),
        )
        op.create_index(
            "ix_balance_transactions_bot_user_id",
            "balance_transactions",
            ["bot_user_id"],
        )
        op.create_index(
            "ix_balance_transactions_bot_user_created",
            "balance_transactions",
            ["bot_user_id", "created_at"],
        )

    # 4. Add topup_notify_on_paid to notification_settings
    notif_columns = [c["name"] for c in inspector.get_columns("notification_settings")]
    if "topup_notify_on_paid" not in notif_columns:
        op.add_column(
            "notification_settings",
            sa.Column("topup_notify_on_paid", sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 4. Remove topup_notify_on_paid from notification_settings
    notif_columns = [c["name"] for c in inspector.get_columns("notification_settings")]
    if "topup_notify_on_paid" in notif_columns:
        op.drop_column("notification_settings", "topup_notify_on_paid")

    # 3. Drop balance_transactions table
    if "balance_transactions" in existing_tables:
        op.drop_index("ix_balance_transactions_bot_user_created", table_name="balance_transactions")
        op.drop_index("ix_balance_transactions_bot_user_id", table_name="balance_transactions")
        op.drop_table("balance_transactions")

    # 2. Drop topup_orders table
    if "topup_orders" in existing_tables:
        op.drop_table("topup_orders")

    # 1. Remove balance column from bot_users
    bot_user_columns = [c["name"] for c in inspector.get_columns("bot_users")]
    if "balance" in bot_user_columns:
        op.drop_column("bot_users", "balance")
