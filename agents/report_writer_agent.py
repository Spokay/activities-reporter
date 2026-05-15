from strands import Agent
from strands.models import AnthropicModel
from config import get_settings

_SYSTEM = (
    "You are a travel report writer. Format research findings into a structured "
    "markdown report with sections: Overview, Top Events, Food & Nightlife, "
    "Day-by-Day Activities, Practical Tips."
)


def create_writer_agent() -> Agent:
    s = get_settings()
    return Agent(
        model=AnthropicModel(
            model_id="claude-sonnet-4-6",
            max_tokens=8192,
            client_args={"api_key": s.anthropic_api_key},
        ),
        tools=[],
        system_prompt=_SYSTEM,
        callback_handler=None,
    )
