-- DailySpend: create the application schema user on Oracle 23ai Free.
--
-- Run once as SYSTEM/SYS, connected to the pluggable database that serves the
-- app (on this machine the listener answers both FREE and FREEPDB1):
--
--   sqlplus system@//localhost:1521/FREEPDB1 @scripts/setup-oracle.sql
--
-- Then set DS_DATABASE_URL accordingly:
--
--   oracle+oracledb://dailyspend:YourPassword@localhost:1521/?service_name=FREEPDB1
--
-- and create the tables with:
--
--   scripts\dev.ps1 -m flask --app wsgi:app db upgrade

-- The app talks to its own schema, never to SYSTEM/SYS.
-- Replace CHANGE_ME before running this file (it is a placeholder, not a secret).
CREATE USER dailyspend IDENTIFIED BY "CHANGE_ME_before_running";

-- Only what the application actually needs.
GRANT CREATE SESSION TO dailyspend;
GRANT CREATE TABLE TO dailyspend;
GRANT CREATE SEQUENCE TO dailyspend;
GRANT CREATE TRIGGER TO dailyspend;

-- Storage quota on the default tablespace used by Oracle 23ai Free.
ALTER USER dailyspend QUOTA UNLIMITED ON USERS;

-- Optional: keep the schema tidy when sessions are killed.
ALTER PROFILE DEFAULT LIMIT IDLE_TIME UNLIMITED;

-- Verification (run after the migration):
--   SELECT table_name FROM user_tables ORDER BY table_name;
--   SELECT version_num FROM "alembic_version";
