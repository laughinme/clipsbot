"""refactor archive into canonical corpus

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-03-25 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("embedding_jobs")
    op.drop_table("telegram_messages")
    op.drop_table("media_assets")
    op.drop_table("telegram_imports")

    op.create_table(
        "source_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_connections_kind", "source_connections", ["kind"], unique=False)
    op.create_index("ix_source_connections_slug", "source_connections", ["slug"], unique=True)
    op.create_index("ix_source_connections_status", "source_connections", ["status"], unique=False)

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_kind", sa.String(length=32), nullable=False),
        sa.Column("coverage_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("raw_manifest_object_key", sa.String(length=1024), nullable=True),
        sa.Column("sample_percent", sa.Integer(), nullable=True),
        sa.Column("include_content_types", sa.Text(), nullable=True),
        sa.Column("exclude_content_types", sa.Text(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_id"], ["source_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_source_id", "sync_runs", ["source_id"], unique=False)
    op.create_index("ix_sync_runs_trigger_kind", "sync_runs", ["trigger_kind"], unique=False)
    op.create_index("ix_sync_runs_coverage_kind", "sync_runs", ["coverage_kind"], unique=False)
    op.create_index("ix_sync_runs_status", "sync_runs", ["status"], unique=False)

    op.create_table(
        "corpus_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_key", sa.String(length=512), nullable=False),
        sa.Column("stable_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("author_external_id", sa.String(length=255), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("container_external_id", sa.String(length=255), nullable=True),
        sa.Column("container_name", sa.String(length=255), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("reply_to_external_key", sa.String(length=512), nullable=True),
        sa.Column("has_media", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("present_in_latest_sync", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_run_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["last_seen_run_id"], ["sync_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["source_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_key", name="uq_corpus_items_source_external_key"),
    )
    op.create_index("ix_corpus_items_source_id", "corpus_items", ["source_id"], unique=False)
    op.create_index("ix_corpus_items_stable_key", "corpus_items", ["stable_key"], unique=True)
    op.create_index("ix_corpus_items_content_hash", "corpus_items", ["content_hash"], unique=False)
    op.create_index("ix_corpus_items_content_type", "corpus_items", ["content_type"], unique=False)
    op.create_index("ix_corpus_items_occurred_at", "corpus_items", ["occurred_at"], unique=False)
    op.create_index("ix_corpus_items_author_external_id", "corpus_items", ["author_external_id"], unique=False)
    op.create_index("ix_corpus_items_container_external_id", "corpus_items", ["container_external_id"], unique=False)
    op.create_index("ix_corpus_items_present_in_latest_sync", "corpus_items", ["present_in_latest_sync"], unique=False)
    op.create_index("ix_corpus_items_last_seen_at", "corpus_items", ["last_seen_at"], unique=False)
    op.create_index("ix_corpus_items_last_seen_run_id", "corpus_items", ["last_seen_run_id"], unique=False)

    op.create_table(
        "corpus_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("corpus_item_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="primary"),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("source_relative_path", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["corpus_item_id"], ["corpus_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_item_id", "role", name="uq_corpus_assets_item_role"),
    )
    op.create_index("ix_corpus_assets_corpus_item_id", "corpus_assets", ["corpus_item_id"], unique=False)
    op.create_index("ix_corpus_assets_role", "corpus_assets", ["role"], unique=False)
    op.create_index("ix_corpus_assets_object_key", "corpus_assets", ["object_key"], unique=False)
    op.create_index("ix_corpus_assets_sha256", "corpus_assets", ["sha256"], unique=False)

    op.create_table(
        "corpus_projections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("corpus_item_id", sa.Uuid(), nullable=False),
        sa.Column("projection_kind", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("qdrant_point_id", sa.String(length=255), nullable=True),
        sa.Column("index_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["corpus_item_id"], ["corpus_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_item_id", "projection_kind", name="uq_corpus_projections_item_kind"),
    )
    op.create_index("ix_corpus_projections_corpus_item_id", "corpus_projections", ["corpus_item_id"], unique=False)
    op.create_index("ix_corpus_projections_projection_kind", "corpus_projections", ["projection_kind"], unique=False)
    op.create_index("ix_corpus_projections_qdrant_point_id", "corpus_projections", ["qdrant_point_id"], unique=True)
    op.create_index("ix_corpus_projections_index_status", "corpus_projections", ["index_status"], unique=False)

    op.create_table(
        "indexing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("projection_id", sa.Uuid(), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=False),
        sa.Column("job_kind", sa.String(length=64), nullable=False, server_default="index_projection"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["projection_id"], ["corpus_projections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["sync_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_indexing_jobs_projection_id", "indexing_jobs", ["projection_id"], unique=False)
    op.create_index("ix_indexing_jobs_sync_run_id", "indexing_jobs", ["sync_run_id"], unique=False)
    op.create_index("ix_indexing_jobs_status", "indexing_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_indexing_jobs_status", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_sync_run_id", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_projection_id", table_name="indexing_jobs")
    op.drop_table("indexing_jobs")

    op.drop_index("ix_corpus_projections_index_status", table_name="corpus_projections")
    op.drop_index("ix_corpus_projections_qdrant_point_id", table_name="corpus_projections")
    op.drop_index("ix_corpus_projections_projection_kind", table_name="corpus_projections")
    op.drop_index("ix_corpus_projections_corpus_item_id", table_name="corpus_projections")
    op.drop_table("corpus_projections")

    op.drop_index("ix_corpus_assets_sha256", table_name="corpus_assets")
    op.drop_index("ix_corpus_assets_object_key", table_name="corpus_assets")
    op.drop_index("ix_corpus_assets_role", table_name="corpus_assets")
    op.drop_index("ix_corpus_assets_corpus_item_id", table_name="corpus_assets")
    op.drop_table("corpus_assets")

    op.drop_index("ix_corpus_items_last_seen_run_id", table_name="corpus_items")
    op.drop_index("ix_corpus_items_last_seen_at", table_name="corpus_items")
    op.drop_index("ix_corpus_items_present_in_latest_sync", table_name="corpus_items")
    op.drop_index("ix_corpus_items_container_external_id", table_name="corpus_items")
    op.drop_index("ix_corpus_items_author_external_id", table_name="corpus_items")
    op.drop_index("ix_corpus_items_occurred_at", table_name="corpus_items")
    op.drop_index("ix_corpus_items_content_type", table_name="corpus_items")
    op.drop_index("ix_corpus_items_content_hash", table_name="corpus_items")
    op.drop_index("ix_corpus_items_stable_key", table_name="corpus_items")
    op.drop_index("ix_corpus_items_source_id", table_name="corpus_items")
    op.drop_table("corpus_items")

    op.drop_index("ix_sync_runs_status", table_name="sync_runs")
    op.drop_index("ix_sync_runs_coverage_kind", table_name="sync_runs")
    op.drop_index("ix_sync_runs_trigger_kind", table_name="sync_runs")
    op.drop_index("ix_sync_runs_source_id", table_name="sync_runs")
    op.drop_table("sync_runs")

    op.drop_index("ix_source_connections_status", table_name="source_connections")
    op.drop_index("ix_source_connections_slug", table_name="source_connections")
    op.drop_index("ix_source_connections_kind", table_name="source_connections")
    op.drop_table("source_connections")

    op.create_table(
        "telegram_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_manifest_object_key", sa.String(length=1024), nullable=True),
        sa.Column("sample_percent", sa.Integer(), nullable=True),
        sa.Column("include_message_types", sa.Text(), nullable=True),
        sa.Column("exclude_message_types", sa.Text(), nullable=True),
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
