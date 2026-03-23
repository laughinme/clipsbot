"""add uploader invites

Revision ID: c1d2e3f4a5b6
Revises: b9f8f4d5a1c2
Create Date: 2026-03-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b9f8f4d5a1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploader_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("consumed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["consumed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploader_invites_token", "uploader_invites", ["token"], unique=True)
    op.create_index("ix_uploader_invites_status", "uploader_invites", ["status"], unique=False)
    op.create_index("ix_uploader_invites_expires_at", "uploader_invites", ["expires_at"], unique=False)
    op.create_index("ix_uploader_invites_created_by_user_id", "uploader_invites", ["created_by_user_id"], unique=False)
    op.create_index("ix_uploader_invites_consumed_by_user_id", "uploader_invites", ["consumed_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_uploader_invites_consumed_by_user_id", table_name="uploader_invites")
    op.drop_index("ix_uploader_invites_created_by_user_id", table_name="uploader_invites")
    op.drop_index("ix_uploader_invites_expires_at", table_name="uploader_invites")
    op.drop_index("ix_uploader_invites_status", table_name="uploader_invites")
    op.drop_index("ix_uploader_invites_token", table_name="uploader_invites")
    op.drop_table("uploader_invites")
