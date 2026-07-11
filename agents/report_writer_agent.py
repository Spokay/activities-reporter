from strands import Agent
from strands.models import AnthropicModel
from config import get_settings

_SYSTEM = (
    "You are a travel report writer. Format research findings into a concise report "
    "strictly under 1500 characters total (including spaces). "
    "Structure: one-line intro, then bullet points (• ) for top 5 events/activities with date and location, "
    "then 2-3 practical tips. No markdown headers, no sections, no extra formatting. "
    "Be specific: names, dates, addresses. Cut filler words. Every character counts."
)


def create_writer_agent() -> Agent:
    s = get_settings()
    return Agent(
        model=AnthropicModel(
            model_id="claude-sonnet-4-6",
            max_tokens=1024,
            client_args={"api_key": s.anthropic_api_key},
        ),
        tools=[],
        system_prompt=_SYSTEM,
        callback_handler=None,
    )
