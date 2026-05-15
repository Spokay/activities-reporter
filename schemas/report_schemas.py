from datetime import date
from typing import Optional
from pydantic import BaseModel
from database.models import ReportStatus


class CreateReportRequest(BaseModel):
    city: str
    start_date: date
    end_date: date


class ReportResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    city: str
    start_date: date
    end_date: date
    status: ReportStatus
    content: Optional[str] = None
    error_message: Optional[str] = None
