#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE PUBLICATION dbz_publication FOR ALL TABLES;

    CREATE ROLE streaming_user WITH REPLICATION LOGIN PASSWORD 'streaming_password';
    GRANT CONNECT ON DATABASE novel_agent TO streaming_user;
    GRANT USAGE ON SCHEMA public TO streaming_user;
    GRANT SELECT ALL TABLES IN SCHEMA public TO streaming_user;

    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

    ALTER SYSTEM SET max_connections = 200;
    ALTER SYSTEM SET shared_buffers = '512MB';
    ALTER SYSTEM SET effective_cache_size = '1GB';
    ALTER SYSTEM SET maintenance_work_mem = '128MB';
    ALTER SYSTEM SET wal_level = 'replica';
    ALTER SYSTEM SET max_wal_senders = 10;
    ALTER SYSTEM SET hot_standby = on;
    ALTER SYSTEM SET wal_keep_size = 256;
EOSQL