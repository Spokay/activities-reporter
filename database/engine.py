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
    _seed_defaults()


def get_engine():
    return _engine


def _seed_defaults():
    from .models import AgentConfig
    from agents.researcher_agent import DEFAULT_SYSTEM_PROMPT as RESEARCHER_PROMPT
    from agents.report_writer_agent import DEFAULT_SYSTEM_PROMPT as WRITER_PROMPT, DEFAULT_MAX_CHARS

    defaults = [
        AgentConfig(
            key="researcher_prompt",
            value=RESEARCHER_PROMPT,
            description="System prompt for the researcher agent (Tavily search)",
        ),
        AgentConfig(
            key="writer_prompt",
            value=WRITER_PROMPT,
            description="System prompt for the report writer agent",
        ),
        AgentConfig(
            key="writer_max_chars",
            value=str(DEFAULT_MAX_CHARS),
            description="Maximum characters allowed in the final report",
        ),
    ]

    with _SessionLocal() as db:
        for entry in defaults:
            if not db.get(AgentConfig, entry.key):
                db.add(entry)
        db.commit()


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
