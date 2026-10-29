"""
services/llm_provider.py — Single resolution point for the active LLM backend.

Why this exists
---------------
Three interchangeable services (Ollama / Claude / OpenAI) expose the same
chat / stream_chat / extract_prd_json / build_system_prompt interface. Two
callers need "the configured one": prd_generator (chat PRD generation) and
mirofish_service (stakeholder proposals). Resolving the provider here keeps
them from drifting apart on the same `settings.llm_provider` value.

Resolution is LAZY and cached. It must not happen at import time: constructing
`openai.AsyncOpenAI` with an empty api_key raises immediately, so eagerly
building every provider crashes app startup for anyone who configured only one
of them (AGENTS.md: "앱 기동 최우선").
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_cache: dict[str, Any] = {}


def get_llm_service() -> Any:
    """
    Return the LLM service for settings.llm_provider, building it on first use.

    Cached per provider name so a single process reuses one client (and so
    tests that monkeypatch the setting still get the right backend).
    """
    provider = settings.llm_provider
    if provider not in _cache:
        _cache[provider] = _build(provider)
    return _cache[provider]


def _build(provider: str) -> Any:
    # Imported lazily: each module constructs its SDK client at __init__, and
    # importing all three up front would require credentials for all three.
    if provider == "claude":
        from app.services.claude_llm_service import ClaudeLLMService

        return ClaudeLLMService()
    if provider == "openai":
        from app.services.openai_llm_service import OpenAILLMService

        return OpenAILLMService()

    from app.services.ollama_llm_service import OllamaLLMService

    return OllamaLLMService()


def reset_cache() -> None:
    """Drop cached services. For tests that switch llm_provider at runtime."""
    _cache.clear()
