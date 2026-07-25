from db.dialects.base import Dialect

WEEKDAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday")


class SqliteDialect(Dialect):
    name = "sqlite"
    placeholder = "?"
    timestamp_type = "DATETIME"
    serial_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"

    def hour_of(self, column):
        return f"CAST(strftime('%H', {column}) AS INTEGER)"

    def weekday_name_of(self, column):
        cases = " ".join(f"WHEN '{i}' THEN '{name}'"
                         for i, name in enumerate(WEEKDAY_NAMES))
        return f"CASE strftime('%w', {column}) {cases} END"

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
