"""Tests for the database adapter module."""

import os
import sqlite3

import pytest

from database.adapter import _convert_placeholders, get_connection, is_postgres


class TestIsPostgres:
    """Tests for is_postgres() detection."""

    def test_returns_false_when_no_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert is_postgres() is False

    def test_returns_false_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "")
        assert is_postgres() is False

    def test_returns_true_when_set(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/testdb")
        assert is_postgres() is True


class TestConvertPlaceholders:
    """Tests for ? → %s placeholder conversion."""

    def test_no_placeholders(self):
        sql = "SELECT * FROM jobs"
        assert _convert_placeholders(sql) == sql

    def test_single_placeholder(self):
        assert _convert_placeholders("SELECT * FROM jobs WHERE uid = ?") == \
            "SELECT * FROM jobs WHERE uid = %s"

    def test_multiple_placeholders(self):
        sql = "INSERT INTO jobs (uid, title) VALUES (?, ?)"
        expected = "INSERT INTO jobs (uid, title) VALUES (%s, %s)"
        assert _convert_placeholders(sql) == expected

    def test_question_mark_in_single_quotes_preserved(self):
        sql = "SELECT * FROM jobs WHERE title LIKE '?%' AND uid = ?"
        expected = "SELECT * FROM jobs WHERE title LIKE '?%' AND uid = %s"
        assert _convert_placeholders(sql) == expected

    def test_question_mark_in_double_quotes_preserved(self):
        sql = 'SELECT * FROM jobs WHERE title = "what?" AND uid = ?'
        expected = 'SELECT * FROM jobs WHERE title = "what?" AND uid = %s'
        assert _convert_placeholders(sql) == expected

    def test_empty_sql(self):
        assert _convert_placeholders("") == ""

    def test_only_placeholder(self):
        assert _convert_placeholders("?") == "%s"

    def test_complex_insert_with_many_placeholders(self):
        sql = "INSERT INTO jobs (a, b, c, d, e) VALUES (?, ?, ?, ?, ?)"
        expected = "INSERT INTO jobs (a, b, c, d, e) VALUES (%s, %s, %s, %s, %s)"
        assert _convert_placeholders(sql) == expected


class TestSQLiteConnection:
    """Tests for SQLite connection mode."""

    def test_get_connection_returns_sqlite(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("config.DB_PATH", tmp_path / "test.db")

        conn = get_connection()
        try:
            # Should be a regular sqlite3 connection
            assert isinstance(conn, sqlite3.Connection)
            # Should have row_factory set
            assert conn.row_factory == sqlite3.Row
        finally:
            conn.close()

    def test_sqlite_connection_supports_execute(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("config.DB_PATH", tmp_path / "test.db")

        conn = get_connection()
        try:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES (?)", ("hello",))
            conn.commit()

            row = conn.execute("SELECT * FROM test WHERE name = ?", ("hello",)).fetchone()
            assert row["name"] == "hello"
        finally:
            conn.close()

    def test_sqlite_connection_dict_access(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("config.DB_PATH", tmp_path / "test.db")

        conn = get_connection()
        try:
            conn.execute("CREATE TABLE test (id INTEGER, val TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'abc')")
            conn.commit()

            row = conn.execute("SELECT * FROM test").fetchone()
            # sqlite3.Row supports both index and key access
            assert row["id"] == 1
            assert row["val"] == "abc"
        finally:
            conn.close()


class TestSQLGeneration:
    """Tests for SQL compatibility patterns used across backends."""

    def test_sqlite_upsert_pattern(self, monkeypatch, tmp_path):
        """Test INSERT OR REPLACE pattern works for SQLite."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("config.DB_PATH", tmp_path / "test.db")

        conn = get_connection()
        try:
            conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, val TEXT)")
            conn.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", ("k1", "v1"))
            conn.commit()

            row = conn.execute("SELECT val FROM kv WHERE key = ?", ("k1",)).fetchone()
            assert row["val"] == "v1"

            # Upsert should update
            conn.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", ("k1", "v2"))
            conn.commit()

            row = conn.execute("SELECT val FROM kv WHERE key = ?", ("k1",)).fetchone()
            assert row["val"] == "v2"

            # Only one row
            count = conn.execute("SELECT COUNT(*) as cnt FROM kv").fetchone()
            assert count["cnt"] == 1
        finally:
            conn.close()

    def test_date_like_pattern(self, monkeypatch, tmp_path):
        """Test LIKE-based date filtering works (cross-DB compatible)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("config.DB_PATH", tmp_path / "test.db")

        conn = get_connection()
        try:
            conn.execute("CREATE TABLE events (id INTEGER, created_at TEXT)")
            conn.execute("INSERT INTO events VALUES (1, '2025-01-15 10:30:00')")
            conn.execute("INSERT INTO events VALUES (2, '2025-01-16 09:00:00')")
            conn.commit()

            rows = conn.execute(
                "SELECT * FROM events WHERE created_at LIKE ?",
                ("2025-01-15%",)
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["id"] == 1
        finally:
            conn.close()
