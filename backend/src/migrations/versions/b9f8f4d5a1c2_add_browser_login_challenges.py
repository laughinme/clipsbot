"""add browser login challenges

Revision ID: b9f8f4d5a1c2
Revises: f24c4ce773b3
Create Date: 2026-03-23 13:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9f8f4d5a1c2"
down_revision: Union[str, Sequence[str], None] = "f24c4ce773b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "browser_login_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("telegram_user_payload", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_browser_login_challenges_token", "browser_login_challenges", ["token"], unique=True)
    op.create_index("ix_browser_login_challenges_status", "browser_login_challenges", ["status"], unique=False)
    op.create_index("ix_browser_login_challenges_expires_at", "browser_login_challenges", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_browser_login_challenges_expires_at", table_name="browser_login_challenges")
    op.drop_index("ix_browser_login_challenges_status", table_name="browser_login_challenges")
    op.drop_index("ix_browser_login_challenges_token", table_name="browser_login_challenges")
    op.drop_table("browser_login_challenges")
