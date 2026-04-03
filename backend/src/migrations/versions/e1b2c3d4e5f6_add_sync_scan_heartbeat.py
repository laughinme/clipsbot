"""add scan heartbeat to sync runs

Revision ID: e1b2c3d4e5f6
Revises: c6d7e8f9a0b1
Create Date: 2026-03-31 13:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sync_runs", sa.Column("scan_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE sync_runs
        SET scan_heartbeat_at = updated_at
        WHERE status = 'scanning' AND scan_heartbeat_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("sync_runs", "scan_heartbeat_at")
