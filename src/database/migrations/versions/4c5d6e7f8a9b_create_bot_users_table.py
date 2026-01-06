"""create bot_users table

Revision ID: 4c5d6e7f8a9b
Revises: 3b4c5d6e7f8a
Create Date: 2025-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c5d6e7f8a9b'
down_revision = '3b4c5d6e7f8a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('bot_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('has_started', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bot_users_telegram_user_id', 'bot_users', ['telegram_user_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_bot_users_telegram_user_id', table_name='bot_users')
    op.drop_table('bot_users')

