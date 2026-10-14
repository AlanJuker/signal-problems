import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from signal_problems.infrastructure.database import make_engine

BACKEND = Path(__file__).parent.parent
SAMPLE_CSV = Path(__file__).parent / "fixtures" / "delays_sample.csv"


@pytest.fixture
def database_url(tmp_path: Path) -> Iterator[str]:
    """A migrated database: PostgreSQL when TEST_DATABASE_URL is set (CI), SQLite otherwise."""
    url = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    yield url
    command.downgrade(config, "base")


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    engine = make_engine(database_url)
    yield engine
    engine.dispose()
