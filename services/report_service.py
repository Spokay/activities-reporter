from datetime import date
from database.engine import get_session
from database.models import Report, ReportStatus
from database.config_service import get_agent_config
from agents.researcher_agent import create_researcher_agent, DEFAULT_SYSTEM_PROMPT as DEFAULT_RESEARCHER_PROMPT
from agents.report_writer_agent import create_writer_agent, DEFAULT_SYSTEM_PROMPT as DEFAULT_WRITER_PROMPT, DEFAULT_MAX_CHARS


async def generate_report(report_id: str, city: str, start_date: date, end_date: date):
    with get_session() as db:
        report = db.get(Report, report_id)
        report.status = ReportStatus.running

        researcher_prompt = get_agent_config(db, "researcher_prompt", DEFAULT_RESEARCHER_PROMPT)
        writer_prompt = get_agent_config(db, "writer_prompt", DEFAULT_WRITER_PROMPT)
        max_chars = int(get_agent_config(db, "writer_max_chars", str(DEFAULT_MAX_CHARS)))

    try:
        researcher = create_researcher_agent(system_prompt=researcher_prompt)
        writer = create_writer_agent(system_prompt=writer_prompt, max_chars=max_chars)

        research = await researcher.invoke_async(
            f"Research activities, events, restaurants and attractions in {city} "
            f"from {start_date} to {end_date}."
        )
        final = await writer.invoke_async(
            f"Format this research into a report:\n{research}"
        )
        content = str(final)

        if len(content) > max_chars:
            content = str(await writer.invoke_async(
                f"This report is too long ({len(content)} chars). "
                f"Rewrite it under {max_chars} characters total. Keep only the 3 best events with date/location and 1 tip. "
                f"Original:\n{content}"
            ))

        with get_session() as db:
            report = db.get(Report, report_id)
            report.status = ReportStatus.done
            report.content = content[:max_chars] if len(content) > max_chars else content

    except Exception as exc:
        with get_session() as db:
            report = db.get(Report, report_id)
            report.status = ReportStatus.failed
            report.error_message = str(exc)
