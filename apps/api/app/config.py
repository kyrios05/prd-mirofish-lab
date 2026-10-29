"""
config.py — Application configuration via environment variables.
"""

from typing import Literal

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
        default="gpt-6.1-terra",
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
        description="Enable/Disable real LLM calls entirely (False forces mock mode).",
    )

    # Anthropic Claude API
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key (https://console.anthropic.com). Required when llm_provider='claude'.",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-5",
        description="Claude model used for chat PRD generation and stakeholder proposals.",
    )

    # OpenAI API (real api.openai.com, distinct from the OpenAI-compatible
    # Ollama proxy config above — shares the same OPENAI_API_KEY env var).
    openai_model: str = Field(
        default="gpt-6.1-terra",
        description="OpenAI model used for chat PRD generation and stakeholder proposals when llm_provider='openai'.",
    )
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = Field(
        default="high", description="Reasoning effort for every OpenAI generation request."
    )
    llm_timeout: int = Field(
        default=180,
        description="Maximum seconds to wait for one configured LLM request.",
    )

    # LLM provider selection (chat PRD generation + stakeholder proposals).
    # Only takes effect when ollama_enabled is True.
    # Validated as a Literal so an unknown value fails at startup. Without this,
    # a typo silently falls through to a *different* backend in each call site.
    llm_provider: Literal["openai", "claude", "ollama"] = Field(
        default="openai",
        description="Which LLM backend to use: 'openai', 'claude', or 'ollama'.",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
