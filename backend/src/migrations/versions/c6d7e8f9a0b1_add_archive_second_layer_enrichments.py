"""add archive second layer enrichments

Revision ID: c6d7e8f9a0b1
Revises: f1a2b3c4d5e6
Create Date: 2026-03-25 01:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrichment_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("sync_run_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("source_ids", sa.Text(), nullable=True),
        sa.Column("content_types", sa.Text(), nullable=True),
        sa.Column("present_in_latest_sync", sa.Boolean(), nullable=True),
        sa.Column("sample_percent", sa.Integer(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["sync_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enrichment_runs_source_id", "enrichment_runs", ["source_id"], unique=False)
    op.create_index("ix_enrichment_runs_sync_run_id", "enrichment_runs", ["sync_run_id"], unique=False)
    op.create_index("ix_enrichment_runs_status", "enrichment_runs", ["status"], unique=False)

    op.create_table(
        "corpus_enrichments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("corpus_item_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("enrichment_kind", sa.String(length=64), nullable=False),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("language_code", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="stub"),
        sa.Column("provider_model", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corpus_item_id"], ["corpus_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["corpus_assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_item_id", "enrichment_kind", name="uq_corpus_enrichments_item_kind"),
    )
    op.create_index("ix_corpus_enrichments_corpus_item_id", "corpus_enrichments", ["corpus_item_id"], unique=False)
    op.create_index("ix_corpus_enrichments_source_asset_id", "corpus_enrichments", ["source_asset_id"], unique=False)
    op.create_index("ix_corpus_enrichments_enrichment_kind", "corpus_enrichments", ["enrichment_kind"], unique=False)
    op.create_index("ix_corpus_enrichments_source_content_hash", "corpus_enrichments", ["source_content_hash"], unique=False)
    op.create_index("ix_corpus_enrichments_status", "corpus_enrichments", ["status"], unique=False)

    op.create_table(
        "enrichment_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrichment_run_id", sa.Uuid(), nullable=False),
        sa.Column("corpus_item_id", sa.Uuid(), nullable=False),
        sa.Column("enrichment_kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corpus_item_id"], ["corpus_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrichment_run_id"], ["enrichment_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("enrichment_run_id", "corpus_item_id", "enrichment_kind", name="uq_enrichment_jobs_run_item_kind"),
    )
    op.create_index("ix_enrichment_jobs_enrichment_run_id", "enrichment_jobs", ["enrichment_run_id"], unique=False)
    op.create_index("ix_enrichment_jobs_corpus_item_id", "enrichment_jobs", ["corpus_item_id"], unique=False)
    op.create_index("ix_enrichment_jobs_enrichment_kind", "enrichment_jobs", ["enrichment_kind"], unique=False)
    op.create_index("ix_enrichment_jobs_status", "enrichment_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_enrichment_jobs_status", table_name="enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_enrichment_kind", table_name="enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_corpus_item_id", table_name="enrichment_jobs")
    op.drop_index("ix_enrichment_jobs_enrichment_run_id", table_name="enrichment_jobs")
    op.drop_table("enrichment_jobs")

    op.drop_index("ix_corpus_enrichments_status", table_name="corpus_enrichments")
    op.drop_index("ix_corpus_enrichments_source_content_hash", table_name="corpus_enrichments")
    op.drop_index("ix_corpus_enrichments_enrichment_kind", table_name="corpus_enrichments")
    op.drop_index("ix_corpus_enrichments_source_asset_id", table_name="corpus_enrichments")
    op.drop_index("ix_corpus_enrichments_corpus_item_id", table_name="corpus_enrichments")
    op.drop_table("corpus_enrichments")

    op.drop_index("ix_enrichment_runs_status", table_name="enrichment_runs")
    op.drop_index("ix_enrichment_runs_sync_run_id", table_name="enrichment_runs")
    op.drop_index("ix_enrichment_runs_source_id", table_name="enrichment_runs")
    op.drop_table("enrichment_runs")
