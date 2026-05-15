from datetime import date
from database.engine import get_session
from database.models import Report, ReportStatus
from agents.researcher_agent import create_researcher_agent
from agents.report_writer_agent import create_writer_agent


async def generate_report(report_id: str, city: str, start_date: date, end_date: date):
    with get_session() as db:
        report = db.get(Report, report_id)
        report.status = ReportStatus.running

    try:
        researcher = create_researcher_agent()
        writer = create_writer_agent()

        research = await researcher.invoke_async(
            f"Research activities, events, restaurants and attractions in {city} "
            f"from {start_date} to {end_date}."
        )
        final = await writer.invoke_async(
            f"Format this research into a report:\n{research}"
        )

        with get_session() as db:
            report = db.get(Report, report_id)
            report.status = ReportStatus.done
            report.content = str(final)

    except Exception as exc:
        with get_session() as db:
            report = db.get(Report, report_id)
            report.status = ReportStatus.failed
            report.error_message = str(exc)
