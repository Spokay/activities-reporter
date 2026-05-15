from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import get_settings

_engine = None
_SessionLocal = None


def init_engine():
    global _engine, _SessionLocal
    _engine = create_engine(get_settings().database_url)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    from .models import Base
    Base.metadata.create_all(_engine)


def get_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
