"""add language preferences

Revision ID: 5d6e7f8a9b0c
Revises: 4c5d6e7f8a9b
Create Date: 2025-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d6e7f8a9b0c'
down_revision = '4c5d6e7f8a9b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Check if language column exists in admins table (if table exists), add if not
    if 'admins' in tables:
        admin_columns = [col['name'] for col in inspector.get_columns('admins')]
        if 'language' not in admin_columns:
            op.add_column(
                'admins',
                sa.Column('language', sa.String(), nullable=False, server_default='en'),
            )

    # Check if user_preferences table exists, create if not
    if 'user_preferences' not in tables:
        op.create_table('user_preferences',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
            sa.Column('language', sa.String(), nullable=False, server_default='en'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_user_preferences_telegram_user_id', 'user_preferences', ['telegram_user_id'], unique=True)
    else:
        # Table exists, check if index exists
        indexes = [idx['name'] for idx in inspector.get_indexes('user_preferences')]
        if 'ix_user_preferences_telegram_user_id' not in indexes:
            op.create_index('ix_user_preferences_telegram_user_id', 'user_preferences', ['telegram_user_id'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # Drop user_preferences table if it exists
    if 'user_preferences' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('user_preferences')]
        if 'ix_user_preferences_telegram_user_id' in indexes:
            op.drop_index('ix_user_preferences_telegram_user_id', table_name='user_preferences')
        op.drop_table('user_preferences')
    
    # Remove language column from admins table if it exists
    if 'admins' in tables:
        admin_columns = [col['name'] for col in inspector.get_columns('admins')]
        if 'language' in admin_columns:
            op.drop_column('admins', 'language')

