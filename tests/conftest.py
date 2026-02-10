"""Shared test fixtures."""

import tempfile
from pathlib import Path

import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.schema import initialize_database
from wired_part.database.repository import Repository


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    """Provide an initialized database connection."""
    conn = DatabaseConnection(db_path)
    initialize_database(conn)
    return conn


@pytest.fixture
def repo(db):
    """Provide a repository with an initialized database."""
    return Repository(db)
