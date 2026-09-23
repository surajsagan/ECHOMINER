from collections.abc import Iterator
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker
from .config import get_settings
from .models import Base

_settings = get_settings()
_is_sqlite = _settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
# An in-memory SQLite database lives per-connection, so the test suite needs a
# single shared connection. Postgres uses the normal pool.
_pool = {"poolclass": StaticPool} if ":memory:" in _settings.database_url else {}
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True,
                       connect_args=_connect_args, **_pool)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _fk_on(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all() -> None:
    """Test/bootstrap convenience only. Production schema is managed by Alembic."""
    Base.metadata.create_all(engine)
