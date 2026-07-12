from sqlalchemy.orm import Session
from .models import AgentConfig


def get_agent_config(db: Session, key: str, default: str) -> str:
    row = db.get(AgentConfig, key)
    return row.value if row else default
