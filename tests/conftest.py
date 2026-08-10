import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.db import get_connection


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.duckdb"
    connection = get_connection(db_path)
    yield connection
    connection.close()
