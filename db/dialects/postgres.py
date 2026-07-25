from db.dialects.base import Dialect


class PostgresDialect(Dialect):
    name = "postgres"
    placeholder = "%s"
    timestamp_type = "TIMESTAMP"
    serial_pk = "SERIAL PRIMARY KEY"

    def hour_of(self, column, tz):
        local = f"({column}::timestamptz AT TIME ZONE '{tz}')"
        return f"EXTRACT(HOUR FROM {local})::int"

    def weekday_name_of(self, column, tz):
        local = f"({column}::timestamptz AT TIME ZONE '{tz}')"
        return f"TRIM(to_char({local}, 'Day'))"

    def _local_ts(self, column, tz):
        return f"({column}::timestamptz AT TIME ZONE '{tz}')"

    def local_date(self, column, tz):
        return f"{self._local_ts(column, tz)}::date"

    def local_week_start(self, column, tz):
        local = self._local_ts(column, tz)
        return f"(date_trunc('week', {local} + interval '1 day') - interval '1 day')::date"

    def local_month_start(self, column, tz):
        local = self._local_ts(column, tz)
        return f"date_trunc('month', {local})::date"

    def within_last_days(self, column, days):
        return f"{column} >= (NOW() - INTERVAL '{int(days)} days')::text"

    def since_start_of_year(self, column):
        return f"{column} >= (date_trunc('year', NOW()))::text"

    def insert_ignore(self, table, columns, conflict):
        return (f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({self.placeholders(len(columns))}) "
                f"ON CONFLICT ({conflict}) DO NOTHING")

    def upsert(self, table, columns, conflict, updates):
        assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
        return (f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({self.placeholders(len(columns))}) "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {assignments}")

    def insert_returning_id(self, table, columns):
        return (f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({self.placeholders(len(columns))}) RETURNING id")

    def inserted_id(self, cursor):
        return cursor.fetchone()[0]

    def existing_columns(self, cursor, table):
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = {self.placeholder}",
            (table,),
        )
        return {row[0] for row in cursor.fetchall()}
