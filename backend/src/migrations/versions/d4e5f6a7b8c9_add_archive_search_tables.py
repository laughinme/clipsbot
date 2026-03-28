"""add archive search tables

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-03-24 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_manifest_object_key", sa.String(length=1024), nullable=True),
        sa.Column("total_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_telegram_imports_manifest_sha256", "telegram_imports", ["manifest_sha256"], unique=True)
    op.create_index("ix_telegram_imports_status", "telegram_imports", ["status"], unique=False)

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("source_relative_path", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("media_kind", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["telegram_imports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id", "sha256", name="uq_media_assets_import_sha256"),
    )
    op.create_index("ix_media_assets_import_id", "media_assets", ["import_id"], unique=False)
    op.create_index("ix_media_assets_object_key", "media_assets", ["object_key"], unique=False)
    op.create_index("ix_media_assets_sha256", "media_assets", ["sha256"], unique=False)
    op.create_index("ix_media_assets_media_kind", "media_assets", ["media_kind"], unique=False)

    op.create_table(
        "telegram_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_title", sa.String(length=255), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("reply_to_message_id", sa.BigInteger(), nullable=True),
        sa.Column("has_media", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=True),
        sa.Column("qdrant_point_id", sa.String(length=255), nullable=True),
        sa.Column("index_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["telegram_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id", "telegram_message_id", name="uq_telegram_messages_import_message"),
    )
    op.create_index("ix_telegram_messages_import_id", "telegram_messages", ["import_id"], unique=False)
    op.create_index("ix_telegram_messages_chat_id", "telegram_messages", ["chat_id"], unique=False)
    op.create_index("ix_telegram_messages_telegram_message_id", "telegram_messages", ["telegram_message_id"], unique=False)
    op.create_index("ix_telegram_messages_author_telegram_id", "telegram_messages", ["author_telegram_id"], unique=False)
    op.create_index("ix_telegram_messages_timestamp", "telegram_messages", ["timestamp"], unique=False)
    op.create_index("ix_telegram_messages_message_type", "telegram_messages", ["message_type"], unique=False)
    op.create_index("ix_telegram_messages_reply_to_message_id", "telegram_messages", ["reply_to_message_id"], unique=False)
    op.create_index("ix_telegram_messages_media_asset_id", "telegram_messages", ["media_asset_id"], unique=False)
    op.create_index("ix_telegram_messages_qdrant_point_id", "telegram_messages", ["qdrant_point_id"], unique=True)
    op.create_index("ix_telegram_messages_index_status", "telegram_messages", ["index_status"], unique=False)

    op.create_table(
        "embedding_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=32), server_default="embed_message", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["telegram_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["telegram_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "job_type", name="uq_embedding_jobs_message_job_type"),
    )
    op.create_index("ix_embedding_jobs_import_id", "embedding_jobs", ["import_id"], unique=False)
    op.create_index("ix_embedding_jobs_message_id", "embedding_jobs", ["message_id"], unique=False)
    op.create_index("ix_embedding_jobs_status", "embedding_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_embedding_jobs_status", table_name="embedding_jobs")
    op.drop_index("ix_embedding_jobs_message_id", table_name="embedding_jobs")
    op.drop_index("ix_embedding_jobs_import_id", table_name="embedding_jobs")
    op.drop_table("embedding_jobs")

    op.drop_index("ix_telegram_messages_index_status", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_qdrant_point_id", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_media_asset_id", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_reply_to_message_id", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_message_type", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_timestamp", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_author_telegram_id", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_telegram_message_id", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_chat_id", table_name="telegram_messages")
    op.drop_index("ix_telegram_messages_import_id", table_name="telegram_messages")
    op.drop_table("telegram_messages")

    op.drop_index("ix_media_assets_media_kind", table_name="media_assets")
    op.drop_index("ix_media_assets_sha256", table_name="media_assets")
    op.drop_index("ix_media_assets_object_key", table_name="media_assets")
    op.drop_index("ix_media_assets_import_id", table_name="media_assets")
    op.drop_table("media_assets")

    op.drop_index("ix_telegram_imports_status", table_name="telegram_imports")
    op.drop_index("ix_telegram_imports_manifest_sha256", table_name="telegram_imports")
    op.drop_table("telegram_imports")
