"""add_open_threads_and_history

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260402_0002"
down_revision: Union[str, None] = "20260402_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE open_threads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            planted_chapter INTEGER NOT NULL,
            entity_ref VARCHAR(500) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            potential_tags TEXT[] DEFAULT '{}',
            status VARCHAR(30) NOT NULL DEFAULT 'open',
            payoff_chapter INTEGER,
            payoff_priority DOUBLE PRECISION DEFAULT 0.0 NOT NULL,
            resolution_summary TEXT,
            planted_content TEXT,
            planted_entity_id UUID,
            last_tracked_chapter INTEGER,
            metadata JSONB DEFAULT '{}',
            version INTEGER DEFAULT 1 NOT NULL
        )
    """)
    op.execute("""
        CREATE INDEX ix_open_threads_project_status
        ON open_threads (project_id, status)
    """)
    op.execute("""
        CREATE INDEX ix_open_threads_project_tracking
        ON open_threads (project_id, payoff_priority DESC)
    """)

    op.execute("""
        CREATE TABLE open_thread_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            thread_id UUID NOT NULL REFERENCES open_threads(id) ON DELETE CASCADE,
            chapter INTEGER NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            old_status VARCHAR(30),
            new_status VARCHAR(30),
            delta_priority DOUBLE PRECISION,
            note TEXT
        )
    """)
    op.execute("""
        CREATE INDEX ix_open_thread_history_thread
        ON open_thread_history (thread_id, chapter)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS open_thread_history")
    op.execute("DROP TABLE IF EXISTS open_threads")
