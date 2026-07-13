from strands import Agent
from strands.models import AnthropicModel
from strands_tools import tavily
from config import get_settings

DEFAULT_SYSTEM_PROMPT = (
    "You are a research agent. Use Tavily to find current events in the given city and date range. "
    "Focus: find at least 3 party, club, or nightlife events (raves, themed parties, club nights, rooftop events). "
    "Also find 1 cultural event (expo, concert, theater, museum) and 1 other event (market, sport, food festival, outdoor). "
    "Return raw findings: event name, date, venue/area for each."
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
