from strands import Agent
from strands.models import AnthropicModel
from config import get_settings

DEFAULT_SYSTEM_PROMPT = (
    "You are a WhatsApp notification writer. Format research findings into a message "
    "strictly under 700 characters total (including spaces and emojis). "
    "Format:\n"
    "Line 1: 📍 [City] • [date range]\n"
    "Lines 2-5: • [Event name] – [date] – [venue/area]\n"
    "Last line: 💡 [one practical tip]\n"
    "No headers. No markdown. Plain text only. Be ruthlessly concise. Every character counts."
)

DEFAULT_MAX_CHARS = 700


def create_writer_agent(
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Agent:
    s = get_settings()
    return Agent(
        model=AnthropicModel(
            model_id="claude-sonnet-4-6",
            max_tokens=max(1024, max_chars // 3),
            client_args={"api_key": s.anthropic_api_key},
        ),
        tools=[],
        system_prompt=system_prompt,
        callback_handler=None,
    )
