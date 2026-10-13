#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -v importer_pw="$IMPORTER_PASSWORD" -v reader_pw="$READER_PASSWORD" <<'EOSQL'
CREATE ROLE importer LOGIN PASSWORD :'importer_pw';
GRANT CREATE ON SCHEMA public TO importer;

CREATE ROLE reader LOGIN PASSWORD :'reader_pw';
GRANT USAGE ON SCHEMA public TO reader;
ALTER DEFAULT PRIVILEGES FOR ROLE importer IN SCHEMA public
    GRANT SELECT ON TABLES TO reader;
EOSQL