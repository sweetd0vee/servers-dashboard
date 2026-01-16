#!/bin/bash
set -e

# Create additional databases. The main DB/user come from env vars.
psql -v ON_ERROR_STOP=1 --username "$DB_USER" <<-EOSQL
    CREATE DATABASE server_metrics;
EOSQL
#!/bin/bash
set -e

# Create additional databases. The main DB/user come from env vars.
psql -v ON_ERROR_STOP=1 --username "$DB_USER" <<-EOSQL
    CREATE DATABASE server_metrics;
EOSQL
