#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create the aura_user with password from .env
    CREATE USER aura_user WITH PASSWORD 'aura_secure_pass';
    
    -- Create the aura_mcp database if it doesn't exist
    SELECT 'CREATE DATABASE aura_mcp'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aura_mcp')\gexec
    
    -- Grant all privileges on the database to the user
    GRANT ALL PRIVILEGES ON DATABASE aura_mcp TO aura_user;
    
    -- Connect to aura_mcp database and set up permissions
    \c aura_mcp
    
    -- Grant necessary permissions on the public schema
    GRANT ALL ON SCHEMA public TO aura_user;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aura_user;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aura_user;
    
    -- Set default privileges for future objects
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO aura_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO aura_user;
    
    -- Create n8n user with password from .env
    CREATE USER n8n WITH PASSWORD '42Gears@1234';
    GRANT CONNECT ON DATABASE aura_mcp TO n8n;
    GRANT USAGE ON SCHEMA public TO n8n;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO n8n;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO n8n;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO n8n;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO n8n;
EOSQL
