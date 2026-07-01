from typing import List
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from auth.jwt import require_auth
from database.engine import get_db
from database.models import Report, ReportStatus
from schemas.report_schemas import CreateReportRequest, ReportResponse
from services.report_service import generate_report

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("", status_code=202, operation_id="create_report", response_model=ReportResponse)
async def create_report(
    req: CreateReportRequest,
    bg: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    done = (
        db.query(Report)
        .filter(
            Report.city == req.city,
            Report.start_date == req.start_date,
            Report.end_date == req.end_date,
            Report.status == ReportStatus.done,
        )
        .first()
    )
    if done:
        response.status_code = 200
        return ReportResponse.model_validate(done)

    in_progress = db.query(Report).filter(
        Report.city == req.city,
        Report.start_date == req.start_date,
        Report.end_date == req.end_date,
        Report.status.in_([ReportStatus.pending, ReportStatus.running]),
    ).first()
    if in_progress:
        return ReportResponse.model_validate(in_progress)

    report = Report(
        id=str(uuid4()),
        city=req.city,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    bg.add_task(generate_report, report.id, req.city, req.start_date, req.end_date)
    return ReportResponse.model_validate(report)


@router.get("", operation_id="get_reports", response_model=List[ReportResponse])
def get_reports(city: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Report)
    if city:
        q = q.filter(Report.city == city)
    return [ReportResponse.model_validate(r) for r in q.all()]


@router.get("/{report_id}", operation_id="get_report_by_id", response_model=ReportResponse)
def get_report_by_id(report_id: str, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportResponse.model_validate(report)
