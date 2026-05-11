"""Shared pytest fixtures.

Tests run against a real Postgres test database (separate from the dev DB) so
PG-specific types (UUID, ENUM) match production. Each test runs inside one
outer transaction that's rolled back at the end. API requests get fresh
sessions (via savepoints) so the identity map can't leak state between calls.
"""
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.main import create_app
from app.models import Base
from app.services import ai_feedback as ai_feedback_module


def _build_test_db_url() -> str:
    base = settings.DATABASE_URL
    if "/" not in base:
        return base
    head, db_name = base.rsplit("/", 1)
    if "?" in db_name:
        db_name, _, query = db_name.partition("?")
        return f"{head}/{db_name}_test?{query}"
    return f"{head}/{db_name}_test"


def _ensure_test_database_exists(test_url: str) -> None:
    head, test_db_name = test_url.rsplit("/", 1)
    if "?" in test_db_name:
        test_db_name = test_db_name.split("?", 1)[0]
    admin_url = f"{head}/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    test_url = _build_test_db_url()
    _ensure_test_database_exists(test_url)
    engine = create_engine(test_url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def _txn_connection(test_engine: Engine) -> Generator[Connection, None, None]:
    """Per-test outer transaction; rolled back on teardown to discard all writes."""
    connection = test_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def session_factory(_txn_connection: Connection) -> Callable[[], Session]:
    """A sessionmaker bound to the per-test connection.

    Each call returns a fresh session that uses SAVEPOINTs internally — so
    `session.commit()` in API code releases a savepoint without committing the
    outer transaction.
    """
    return sessionmaker(
        bind=_txn_connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture
def db_session(session_factory: Callable[[], Session]) -> Generator[Session, None, None]:
    """A single session for tests that need direct DB access."""
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(session_factory: Callable[[], Session]) -> Generator[TestClient, None, None]:
    """TestClient with overridden DB dep + AI background-task DB pointed at test DB."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    ai_feedback_module.set_session_factory_for_testing(session_factory)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        ai_feedback_module.set_session_factory_for_testing(None)
        app.dependency_overrides.clear()
