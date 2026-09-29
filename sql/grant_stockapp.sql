-- Fix: tables created by postgres during backfill; API connects as stockapp
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tableowner = 'postgres'
  LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO stockapp', r.tablename);
  END LOOP;
END
$$;

GRANT ALL ON ALL TABLES IN SCHEMA public TO stockapp;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO stockapp;
GRANT USAGE ON SCHEMA public TO stockapp;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT ALL ON TABLES TO stockapp;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT ALL ON SEQUENCES TO stockapp;
