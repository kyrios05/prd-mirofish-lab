"""
config.py — Application configuration via environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = Field(default="PRD MiroFish Lab API", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    # MiroFish integration
    mirofish_base_url: str = Field(
        default="http://localhost:9000",
        description="MiroFish simulation service base URL",
    )
    mirofish_api_key: str = Field(
        default="",
        description="MiroFish API key",
    )

    # OpenAI-compatible LLM
    openai_api_base: str = Field(
        default="",
        description="OpenAI-compatible API base URL",
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI-compatible API key",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
