"""Chapter table range partitioning by created_at.

Revision ID: 20260402_0001
Revises: 20260328_0029
Create Date: 2026-04-02 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260402_0001"
down_revision = "20260328_0029"
branch_labels = None
depends_on = None


CHAPTER_PARTITION_INTERVAL = "3 months"


def _build_partition_spec(table_name: str, start_expr: str, end_expr: str) -> str:
    return f"{table_name}_{start_expr.replace(' ', '_').replace('-', '').replace(':', '')} PARTITION OF {table_name} FOR VALUES FROM ({start_expr}) TO ({end_expr})"


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION create_chapter_partition()
        RETURNS void AS $$
        DECLARE
            partition_date DATE;
            start_date DATE;
            end_date DATE;
            partition_name TEXT;
        BEGIN
            partition_date := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '3 months');
            start_date := partition_date;
            end_date := partition_date + INTERVAL '3 months';
            partition_name := 'chapters_' || TO_CHAR(start_date, 'YYYYMMDD');

            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF chapters FOR VALUES FROM (%L) TO (%L)',
                    partition_name, start_date, end_date
                );
                RAISE NOTICE 'Created partition: %', partition_name;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION auto_create_chapter_partitions()
        RETURNS event_trigger AS $$
        DECLARE
            obj record;
        BEGIN
            PERFORM create_chapter_partition();
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE EVENT TRIGGER create_chapter_partition_trigger
        ON ddl_command_end
        WHEN TAG IN ('CREATE TABLE')
        EXECUTE FUNCTION auto_create_chapter_partitions();
    """)

    op.execute(f"""
        CREATE TABLE chapters_partitioned (
            LIKE chapters INCLUDING ALL
            INCLUDING CONSTRAINTS
            INCLUDING DEFAULTS
            INCLUDING INDEXES
        ) PARTITION BY RANGE (created_at);
    """)

    op.execute("""
        INSERT INTO chapters_partitioned
        SELECT * FROM chapters;
    """)

    op.execute("""
        DROP TABLE chapters CASCADE;
        ALTER TABLE chapters_partitioned RENAME TO chapters;
        ALTER TABLE pk_chapters RENAME TO pk_chapters_old;
        ALTER INDEX ix_chapters_project_id RENAME TO ix_chapters_project_id_old;
    """)

    op.execute("""
        DO $$
        DECLARE
            idx RECORD;
        BEGIN
            FOR idx IN SELECT tablename, indexname FROM pg_indexes
                       WHERE tablename = 'chapters' AND indexname LIKE '%_old'
            LOOP
                EXECUTE format('ALTER INDEX %I RENAME TO %I',
                    idx.indexname,
                    REPLACE(idx.indexname, '_old', '')
                );
            END LOOP;
        END $$;
    """)

    op.execute("""
        ALTER INDEX ix_chapters_project_id RENAME TO ix_chapters_project_id_new;
        ALTER INDEX ix_chapters_project_id_new RENAME TO ix_chapters_project_id;
    """)

    op.execute("ALTER TABLE chapters ADD CONSTRAINT pk_chapters PRIMARY KEY USING INDEX ix_chapters_id;")

    op.execute("""
        CREATE TABLE chapters_default PARTITION OF chapters DEFAULT;
    """)

    op.execute("""
        CREATE TABLE chapters_20260401 PARTITION OF chapters
        FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
    """)

    op.execute("""
        CREATE TABLE chapters_20260701 PARTITION OF chapters
        FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');
    """)

    op.execute("""
        CREATE TABLE chapters_20261001 PARTITION OF chapters
        FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');
    """)


def downgrade() -> None:
    op.execute("DROP EVENT TRIGGER IF EXISTS create_chapter_partition_trigger;")
    op.execute("DROP FUNCTION IF EXISTS auto_create_chapter_partitions();")
    op.execute("DROP FUNCTION IF EXISTS create_chapter_partition();")

    op.execute("""
        CREATE TABLE chapters_unpartitioned (
            LIKE chapters INCLUDING ALL
        );
        INSERT INTO chapters_unpartitioned SELECT * FROM chapters;
        DROP TABLE chapters CASCADE;
        ALTER TABLE chapters_unpartitioned RENAME TO chapters;
        ALTER TABLE pk_chapters_old RENAME TO pk_chapters;
    """)
