"""Database adapter for SQLite and PostgreSQL compatibility.

Provides a uniform interface for both database backends. PostgreSQL is used
when the DATABASE_URL environment variable is set; otherwise falls back to SQLite.

Usage:
    from database.adapter import get_connection, is_postgres

    conn = get_connection()
    conn.execute("SELECT * FROM jobs WHERE uid = ?", (uid,))  # ? auto-converted to %s for PG
    conn.commit()
    conn.close()
"""

import os
import logging

log = logging.getLogger(__name__)


def is_postgres() -> bool:
    """Check if PostgreSQL backend is active (DATABASE_URL is set)."""
    return bool(os.environ.get("DATABASE_URL", ""))


def get_connection():
    """Get a database connection (SQLite or PostgreSQL).

    Returns a connection with a uniform interface:
    - conn.execute(sql, params) works with ? placeholders (auto-converted for PG)
    - conn.commit() / conn.close()
    - cursor.fetchone() / cursor.fetchall() return dict-like rows
    """
    if is_postgres():
        return _get_postgres_connection()
    else:
        return _get_sqlite_connection()


def _get_sqlite_connection():
    """Get a SQLite connection with WAL mode and row factory."""
    import sqlite3
    import config

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_postgres_connection():
    """Get a PostgreSQL connection wrapped for SQLite-compatible interface."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = os.environ["DATABASE_URL"]
    raw_conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    return _PGConnectionWrapper(raw_conn)


class _PGConnectionWrapper:
    """Wraps a psycopg2 connection to provide an SQLite-like interface.

    Key differences handled:
    - Converts ? placeholders to %s
    - conn.execute() creates a cursor and returns it (like SQLite)
    - Rows are RealDictRow (dict-like, works with dict())
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        """Execute SQL, converting ? placeholders to %s for PostgreSQL."""
        sql = _convert_placeholders(sql)
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def rollback(self):
        self._conn.rollback()


def _convert_placeholders(sql: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL %s placeholders.

    Handles ? inside string literals by tracking quote state.
    """
    result = []
    in_string = False
    quote_char = None

    for char in sql:
        if char in ("'", '"') and not in_string:
            in_string = True
            quote_char = char
            result.append(char)
        elif char == quote_char and in_string:
            in_string = False
            quote_char = None
            result.append(char)
        elif char == "?" and not in_string:
            result.append("%s")
        else:
            result.append(char)

    return "".join(result)
