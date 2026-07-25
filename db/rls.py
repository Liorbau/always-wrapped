"""Enable Postgres RLS on backend-only tables in Supabase public schema.

The Flask app connects with a privileged role (DATABASE_URL) that bypasses RLS.
With no policies for anon/authenticated, the Supabase Data API is denied while
the server keeps read/write access.
"""


def enable_rls(cursor, driver, table):
    if driver != "postgres":
        return
    cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
