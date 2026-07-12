from strands import Agent
from strands.models import AnthropicModel
from strands_tools import tavily
from config import get_settings

DEFAULT_SYSTEM_PROMPT = (
    "You are a research agent. Use Tavily to find current events, activities, "
    "restaurants, and attractions for the given city and date range. "
    "Return comprehensive, raw findings."
)


def create_researcher_agent(system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> Agent:
    s = get_settings()
    return Agent(
        model=AnthropicModel(
            model_id="claude-haiku-4-5-20251001",
            max_tokens=4096,
            client_args={"api_key": s.anthropic_api_key},
        ),
        tools=[tavily],
        system_prompt=system_prompt,
        callback_handler=None,
    )
