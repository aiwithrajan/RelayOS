"""Pytest configuration and fixtures for RelayOS."""
import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Use an isolated SQLite test database to prevent lock conflicts with the running server."""
    with tempfile.NamedTemporaryFile(suffix="_relayos_test.db", delete=False) as tmp:
        test_db_path = tmp.name

    os.environ["RELAYOS_DB_PATH"] = test_db_path

    # Initialize test DB
    from core.database import init_db
    init_db()

    yield test_db_path

    # Cleanup test DB
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass
