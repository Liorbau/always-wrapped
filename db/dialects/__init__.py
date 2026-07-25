"""Dialect registry.

    dialect_for("postgres") -> PostgresDialect
    dialect_for("sqlite")   -> SqliteDialect
"""

from db.dialects.base import Dialect
from db.dialects.postgres import PostgresDialect
from db.dialects.sqlite import SqliteDialect

DIALECTS = {
    PostgresDialect.name: PostgresDialect(),
    SqliteDialect.name: SqliteDialect(),
}

__all__ = ["Dialect", "PostgresDialect", "SqliteDialect", "DIALECTS", "dialect_for"]


def dialect_for(driver):
    """Accepts a driver name or an already-resolved Dialect."""
    if isinstance(driver, Dialect):
        return driver
    try:
        return DIALECTS[driver]
    except KeyError:
        raise ValueError(
            f"Unsupported database driver {driver!r}; expected one of {sorted(DIALECTS)}"
        ) from None
