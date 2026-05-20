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
        default="http://localhost:5001",
        description="MiroFish simulation service base URL",
    )
    mirofish_api_key: str = Field(
        default="",
        description="MiroFish API key",
    )

    # T10: MiroFish adapter mode and tuning
    mirofish_mode: str = Field(
        default="mock",
        description=(
            "Validation engine mode. "
            "'mock' → run_mock_validation() (default, no external I/O). "
            "'live' → real MiroFish HTTP call via MiroFishAdapter."
        ),
    )
    mirofish_timeout: int = Field(
        default=30,
        description="Per-request HTTP timeout in seconds for MiroFish calls.",
    )
    mirofish_max_retries: int = Field(
        default=3,
        description="Max HTTP retry attempts per MiroFish API call.",
    )
    mirofish_polling_interval: float = Field(
        default=2.0,
        description="Seconds between polling attempts for async MiroFish jobs.",
    )
    mirofish_max_polling: int = Field(
        default=150,
        description=(
            "Maximum number of polling attempts before declaring a timeout. "
            "At polling_interval=2.0 this gives a ~5-minute ceiling."
        ),
    )
    mirofish_fallback_to_mock: bool = Field(
        default=True,
        description=(
            "When mode='live' and the MiroFish adapter raises an unrecoverable "
            "error, fall back to run_mock_validation() instead of propagating "
            "the error to the caller."
        ),
    )

    # Simulation Tuning
    mirofish_max_rounds: int = Field(
        default=50,
        description="Maximum simulation rounds for MiroFish engine.",
    )
    mirofish_enable_memory: bool = Field(
        default=True,
        description="Enable knowledge graph memory updates for agents during simulation.",
    )
    mirofish_agent_count: int = Field(
        default=10,
        description="Target number of agents to participate in simulation.",
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
    openai_model_name: str = Field(
        default="qwen3.5:27b",
        description="LLM model name to use for analysis.",
    )

    # Ollama Local LLM
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama local API base URL",
    )
    ollama_model: str = Field(
        default="qwen3.5:27b",
        description="Ollama model name to use for PRD generation.",
    )
    ollama_timeout: int = Field(
        default=300,
        description="Timeout in seconds for Ollama LLM requests.",
    )
    ollama_enabled: bool = Field(
        default=True,
        description="Enable/Disable local Ollama LLM (False forces mock mode).",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
