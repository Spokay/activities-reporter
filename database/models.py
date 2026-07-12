import enum
import uuid
from sqlalchemy import Column, String, Date, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class ReportStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done    = "done"
    failed  = "failed"


class Base(DeclarativeBase):
    pass


class Report(Base):
    __tablename__ = "reports"

    id            = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    city          = Column(String(255), nullable=False)
    start_date    = Column(Date, nullable=False)
    end_date      = Column(Date, nullable=False)
    status        = Column(SAEnum(ReportStatus), default=ReportStatus.pending, nullable=False)
    content       = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AgentConfig(Base):
    __tablename__ = "agent_config"

    key         = Column(String(100), primary_key=True)
    value       = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
