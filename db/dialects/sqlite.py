from db.dialects.base import Dialect


class SqliteDialect(Dialect):
    name = "sqlite"
    placeholder = "?"
    timestamp_type = "DATETIME"
    serial_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"

    def hour_of(self, column, tz):
        return f"local_hour({column}, '{tz}')"

    def weekday_name_of(self, column, tz):
        return f"local_weekday({column}, '{tz}')"

    def local_date(self, column, tz):
        return f"local_date({column}, '{tz}')"

    def local_week_start(self, column, tz):
        return f"local_week_start({column}, '{tz}')"

    def local_month_start(self, column, tz):
        return f"local_month_start({column}, '{tz}')"

    def within_last_days(self, column, days):
        return f"{column} >= datetime('now', '-{int(days)} days')"

    def since_start_of_year(self, column):
        return f"{column} >= datetime('now', 'start of year')"

    def insert_ignore(self, table, columns, conflict):
        return (f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) "
                f"VALUES ({self.placeholders(len(columns))})")

    def upsert(self, table, columns, conflict, updates):
        return (f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) "
                f"VALUES ({self.placeholders(len(columns))})")

    def insert_returning_id(self, table, columns):
        return (f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({self.placeholders(len(columns))})")

    def inserted_id(self, cursor):
        return cursor.lastrowid

    def existing_columns(self, cursor, table):
        # PRAGMA takes no parameters; table names here are literals in our code,
        # never user input.
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}
