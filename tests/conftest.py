import os
import tempfile

import pytest

from database import DatabaseManager


@pytest.fixture
def tmp_db_path():
    """Provides a temporary file path for a test database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def db_manager(tmp_db_path):
    """Provides a fresh DatabaseManager pointing to a temporary DB."""
    # Create the instance, manually set the db path, THEN init
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.main_db = tmp_db_path
    manager._conn_cache = {}

    # Manually mimic the init, skipping jamdict for speed/safety in tests
    # Or just calling init_main_db safely
    manager.jam = None
    manager.init_main_db()
    return manager

@pytest.fixture
def mock_config():
    """Provides a mock configuration object."""
    class MockConfig:
        def __init__(self):
            self.font_size = 12
            self.history_size = 10
            self.extra_dictionaries = []
    return MockConfig()
