from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    database_url: str = "sqlite:///./activities.db"
    anthropic_api_key: str
    tavily_api_key: str

    oauth_issuer: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_audience: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
