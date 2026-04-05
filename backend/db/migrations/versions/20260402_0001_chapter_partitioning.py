"""Chapter partitioning compatibility migration.

Revision ID: 20260402_0001
Revises: 20260328_0029
Create Date: 2026-04-02 00:00:00

The original partitioning plan attempted to replace the existing ``chapters``
table with a range-partitioned variant. In practice that DDL is not valid for
the current schema because the primary key does not include the partition key
(``created_at``), which makes fresh database setup fail.

Current runtime behavior does not depend on physical partitioning, so this
revision is intentionally reduced to a no-op compatibility marker to keep the
migration chain usable on clean databases.
"""

from __future__ import annotations

from alembic import op


revision = "20260402_0001"
down_revision = "20260328_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SELECT 1")


def downgrade() -> None:
    op.execute("SELECT 1")
