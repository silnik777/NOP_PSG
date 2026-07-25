"""Shared pytest fixtures: isolated in-memory DB and a FastAPI test client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    # Bind persistence to a private in-memory SQLite for each test.
    import egsd.infrastructure.persistence.database as db
    from egsd.infrastructure.persistence.models import Base
    from egsd.infrastructure.persistence.seed import seed_reference_data

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    Base.metadata.create_all(engine)
    with TestingSession() as s:
        seed_reference_data(s)
        s.commit()

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", TestingSession)

    from egsd.api.main import app

    def override_get_session():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db.get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
