"""add archive import selection fields

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-03-24 19:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("telegram_imports", sa.Column("sample_percent", sa.Integer(), nullable=True))
    op.add_column("telegram_imports", sa.Column("include_message_types", sa.Text(), nullable=True))
    op.add_column("telegram_imports", sa.Column("exclude_message_types", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("telegram_imports", "exclude_message_types")
    op.drop_column("telegram_imports", "include_message_types")
    op.drop_column("telegram_imports", "sample_percent")
