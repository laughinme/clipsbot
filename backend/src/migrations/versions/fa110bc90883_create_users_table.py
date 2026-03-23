"""create users tables

Revision ID: 4199fbff849e
Revises: 
Create Date: 2025-11-07 03:11:11.699600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4199fbff849e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('telegram_id', sa.BigInteger(), nullable=True),
    sa.Column('telegram_username', sa.String(length=255), nullable=True),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('avatar_key', sa.String(length=512), nullable=True),
    sa.Column('telegram_avatar_file_unique_id', sa.String(length=255), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('banned', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    sa.Column('auth_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('users_username_trgm', 'users', ['username'], unique=False, postgresql_using='gin', postgresql_ops={'username': 'gin_trgm_ops'})
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_telegram_id', table_name='users')
    op.drop_index('users_username_trgm', table_name='users', postgresql_using='gin', postgresql_ops={'username': 'gin_trgm_ops'})
    op.drop_table('users')

    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
