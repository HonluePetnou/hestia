"""PostgreSQL + pgvector integration tests.

They run only when HESTIA_TEST_DATABASE_URL points to a database whose name ends with
`_test` (it is wiped and rebuilt with the Alembic migrations). Example:

    createdb hestia_test
    HESTIA_TEST_DATABASE_URL=postgresql+psycopg://hestia:hestia@localhost:5434/hestia_test \
        uv run pytest tests/integration

Without the variable (or when the server is unreachable) every test is skipped, never faked.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[2]
URL = os.getenv("HESTIA_TEST_DATABASE_URL")


def alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env={**os.environ, "DATABASE_URL": URL or ""},
        check=True,
        capture_output=True,
    )


def reset_schema(engine) -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


@pytest.fixture(scope="session")
def engine():
    if not URL:
        pytest.skip("HESTIA_TEST_DATABASE_URL not set: PostgreSQL integration tests skipped")
    if not make_url(URL).database or not make_url(URL).database.endswith("_test"):
        pytest.skip("refusing to wipe a database whose name does not end with _test")
    eng = create_engine(URL)
    try:
        with eng.connect():
            pass
    except Exception as exc:  # server down
        pytest.skip(f"PostgreSQL unreachable: {exc.__class__.__name__}")
    return eng


@pytest.fixture()
def db(engine):
    """Fresh schema at head for every test."""
    reset_schema(engine)
    alembic("upgrade", "head")
    with Session(engine) as session:
        yield session
