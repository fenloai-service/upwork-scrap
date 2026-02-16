"""Database adapter for SQLite and PostgreSQL compatibility.

Provides a uniform interface for both database backends. PostgreSQL is used
when the DATABASE_URL environment variable is set; otherwise falls back to SQLite.

Features:
- PostgreSQL connection pooling (ThreadedConnectionPool, 1-5 connections)
- Automatic ? -> %s placeholder conversion
- Dict-like row access for both backends

Usage:
    from database.adapter import get_connection, is_postgres

    conn = get_connection()
    conn.execute("SELECT * FROM jobs WHERE uid = ?", (uid,))  # ? auto-converted to %s for PG
    conn.commit()
    conn.close()
"""

import os
import logging
import threading

log = logging.getLogger(__name__)

# PostgreSQL connection pool (module-level, lazy-initialized)
_pg_pool = None
_pg_pool_lock = threading.Lock()


def is_postgres() -> bool:
    """Check if PostgreSQL backend is active (DATABASE_URL is set)."""
    return bool(os.environ.get("DATABASE_URL", ""))


def get_connection():
    """Get a database connection (SQLite or PostgreSQL).

    Returns a connection with a uniform interface:
    - conn.execute(sql, params) works with ? placeholders (auto-converted for PG)
    - conn.commit() / conn.close()
    - cursor.fetchone() / cursor.fetchall() return dict-like rows

    For PostgreSQL, connections come from a thread-safe pool.
    close() returns the connection to the pool instead of closing it.
    """
    if is_postgres():
        return _get_pooled_postgres_connection()
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


def _get_or_create_pool():
    """Lazily create the PostgreSQL connection pool (thread-safe)."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    with _pg_pool_lock:
        # Double-check after acquiring lock
        if _pg_pool is not None:
            return _pg_pool

        import psycopg2.pool
        url = os.environ["DATABASE_URL"]
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=url,
        )
        log.info("PostgreSQL connection pool created (1-5 connections)")
        return _pg_pool


def _get_pooled_postgres_connection():
    """Get a PostgreSQL connection from the pool, wrapped for SQLite-compatible interface."""
    from psycopg2.extras import RealDictCursor

    pool = _get_or_create_pool()
    raw_conn = pool.getconn()
    # Set cursor factory on the connection
    raw_conn.cursor_factory = RealDictCursor
    return _PooledPGConnectionWrapper(raw_conn, pool)


def close_pool():
    """Close the PostgreSQL connection pool. Call on shutdown for clean exit."""
    global _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None:
            _pg_pool.closeall()
            _pg_pool = None
            log.info("PostgreSQL connection pool closed")


class _PooledPGConnectionWrapper:
    """Wraps a pooled psycopg2 connection to provide an SQLite-like interface.

    Key differences handled:
    - Converts ? placeholders to %s
    - conn.execute() creates a cursor and returns it (like SQLite)
    - Rows are RealDictRow (dict-like, works with dict())
    - close() returns connection to pool instead of closing it
    """

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def execute(self, sql, params=None):
        """Execute SQL, converting ? placeholders to %s for PostgreSQL."""
        sql = _convert_placeholders(sql)
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        """Return connection to pool instead of closing it."""
        self._pool.putconn(self._conn)

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
