"""Tests for the DatabaseConnection class."""

import sqlite3
import pytest
from pathlib import Path

from wired_part.database.connection import DatabaseConnection


class TestDatabaseConnectionInit:
    def test_creates_db_file_on_connect(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        db_path = tmp_path / "sub" / "deep" / "test.db"
        db = DatabaseConnection(str(db_path))
        assert db_path.parent.exists()

    def test_accepts_pathlib_path(self, tmp_path):
        db_path = tmp_path / "pathlib.db"
        db = DatabaseConnection(db_path)
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        assert db_path.exists()

    def test_db_path_stored(self, tmp_path):
        db_path = tmp_path / "stored.db"
        db = DatabaseConnection(str(db_path))
        assert db.db_path == db_path


class TestGetConnection:
    def test_yields_connection(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "conn.db"))
        with db.get_connection() as conn:
            assert conn is not None

    def test_row_factory_is_row(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "row.db"))
        with db.get_connection() as conn:
            assert conn.row_factory == sqlite3.Row

    def test_foreign_keys_enabled(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "fk.db"))
        with db.get_connection() as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1

    def test_auto_commits(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "commit.db"))
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
            conn.execute("INSERT INTO t (v) VALUES ('hello')")
        # Read back in new connection
        rows = db.execute("SELECT v FROM t")
        assert len(rows) == 1
        assert rows[0]["v"] == "hello"

    def test_rollback_on_exception(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "rollback.db"))
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        db.execute("INSERT INTO t (v) VALUES ('keep')")
        with pytest.raises(RuntimeError):
            with db.get_connection() as conn:
                conn.execute("INSERT INTO t (v) VALUES ('discard')")
                raise RuntimeError("fail")
        rows = db.execute("SELECT v FROM t")
        assert len(rows) == 1
        assert rows[0]["v"] == "keep"

    def test_connection_closed_after_context(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "close.db"))
        with db.get_connection() as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
        # Connection should be closed — attempting to use it should fail
        with pytest.raises(Exception):
            conn.execute("SELECT 1")


class TestExecute:
    def test_returns_rows(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "exec.db"))
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        db.execute("INSERT INTO t (v) VALUES ('a')")
        db.execute("INSERT INTO t (v) VALUES ('b')")
        rows = db.execute("SELECT v FROM t ORDER BY v")
        assert len(rows) == 2
        assert rows[0]["v"] == "a"
        assert rows[1]["v"] == "b"

    def test_with_params(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "params.db"))
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        db.execute("INSERT INTO t (v) VALUES (?)", ("test",))
        rows = db.execute("SELECT v FROM t WHERE v = ?", ("test",))
        assert len(rows) == 1

    def test_returns_empty_for_no_rows(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "empty.db"))
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        rows = db.execute("SELECT * FROM t")
        assert rows == []

    def test_raises_on_bad_sql(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "bad.db"))
        with pytest.raises(Exception):
            db.execute("SELECT * FROM nonexistent_table")


class TestExecuteScript:
    def test_runs_multi_statement(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "script.db"))
        db.execute_script("""
            CREATE TABLE a (id INTEGER PRIMARY KEY);
            CREATE TABLE b (id INTEGER PRIMARY KEY);
            INSERT INTO a (id) VALUES (1);
            INSERT INTO b (id) VALUES (2);
        """)
        rows_a = db.execute("SELECT * FROM a")
        rows_b = db.execute("SELECT * FROM b")
        assert len(rows_a) == 1
        assert len(rows_b) == 1

    def test_raises_on_bad_script(self, tmp_path):
        db = DatabaseConnection(str(tmp_path / "badscript.db"))
        with pytest.raises(Exception):
            db.execute_script("INVALID SQL STATEMENT;")
