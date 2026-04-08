"""Add project phase tracking fields

Revision ID: 20260407_0001
Revises: 20260406_0001
Create Date: 2024-04-07 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260407_0001'
down_revision = '20260406_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'projects',
        sa.Column('initial_idea', sa.Text(), nullable=True),
    )
    op.add_column(
        'projects',
        sa.Column('world_building_completed', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'projects',
        sa.Column('current_phase', sa.String(50), nullable=False, server_default='world-building'),
    )


def downgrade() -> None:
    op.drop_column('projects', 'current_phase')
    op.drop_column('projects', 'world_building_completed')
    op.drop_column('projects', 'initial_idea')
