"""add telegram auth fields and clips tables

Revision ID: f24c4ce773b3
Revises: a629654c84b7
Create Date: 2026-03-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
revision: str = "f24c4ce773b3"
down_revision: Union[str, Sequence[str], None] = "a629654c84b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clips",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("bucket", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clips_slug", "clips", ["slug"], unique=True)
    op.create_index("ix_clips_uploaded_by_user_id", "clips", ["uploaded_by_user_id"], unique=False)

    op.create_table(
        "clip_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("clip_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["clip_id"], ["clips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clip_aliases_clip_id", "clip_aliases", ["clip_id"], unique=False)
    op.create_index("ix_clip_aliases_value", "clip_aliases", ["value"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clip_aliases_value", table_name="clip_aliases")
    op.drop_index("ix_clip_aliases_clip_id", table_name="clip_aliases")
    op.drop_table("clip_aliases")

    op.drop_index("ix_clips_uploaded_by_user_id", table_name="clips")
    op.drop_index("ix_clips_slug", table_name="clips")
    op.drop_table("clips")
