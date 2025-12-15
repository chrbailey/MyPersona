from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # LLM Configuration - Choose ONE: "openai" or "anthropic"
    llm_provider: Literal["openai", "anthropic"] = "anthropic"

    # OpenAI settings
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Anthropic settings
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/oauth/callback"

    # Confidence thresholds (from spec section 5.3)
    calendar_confidence_threshold: float = 0.3
    role_confidence_threshold: float = 0.4

    # LLM constraints
    micro_call_max_tokens: int = 300
    primary_call_max_tokens: int = 2048

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
