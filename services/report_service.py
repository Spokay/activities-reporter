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
        content = str(final)

        if len(content) > 1500:
            content = str(await writer.invoke_async(
                f"This report is too long ({len(content)} chars). "
                f"Rewrite it under 1500 characters total. Keep only the 3 best events with date/location and 1 tip. "
                f"Original:\n{content}"
            ))

        with get_session() as db:
            report = db.get(Report, report_id)
            report.status = ReportStatus.done
            report.content = content[:1500] if len(content) > 1500 else content

    except Exception as exc:
        with get_session() as db:
            report = db.get(Report, report_id)
            report.status = ReportStatus.failed
            report.error_message = str(exc)
