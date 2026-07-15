"""Database engine/session setup and dev-mode schema creation + seed."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ...config import settings
from .models import Base

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create schema (dev mode) and seed reference data if empty."""
    Base.metadata.create_all(engine)
    from .device_seed import seed_device_cards
    from .macro_scenario_seed import seed_macro_scenarios
    from .price_seed import seed_price_series
    from .quality_seed import seed_quality_sets
    from .seed import seed_reference_data

    with SessionLocal() as session:
        seed_reference_data(session)
        seed_device_cards(session)
        seed_price_series(session)
        seed_macro_scenarios(session)
        seed_quality_sets(session)
        session.commit()


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
