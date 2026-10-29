"""
services/claude_llm_service.py — Service for interacting with the Claude API.

Drop-in replacement for OllamaLLMService (same chat/stream_chat/extract_prd_json/
build_system_prompt interface) backed by Anthropic's hosted Claude models instead
of a local Ollama model.
"""

import logging
from typing import Any, Optional

import anthropic
from app.config import settings
from app.services.prompts import build_system_prompt as build_strict_prompt
from app.services.prompts import extract_prd_json

logger = logging.getLogger("app.api.claude")


class ClaudeLLMService:
    """
    Service for interacting with the Claude API to facilitate
    chat-driven PRD generation and stakeholder proposal generation.
    """

    def __init__(self):
        self.model = settings.anthropic_model
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    @staticmethod
    def _split_system(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
        """
        Claude's API takes the system prompt as a separate top-level
        parameter rather than a message with role='system'.
        """
        system_parts: list[str] = []
        turns: list[dict[str, str]] = []
        for message in messages:
            if message["role"] == "system":
                system_parts.append(message["content"])
            else:
                turns.append({"role": message["role"], "content": message["content"]})
        return "\n\n".join(system_parts), turns

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to Claude and return the assistant message content.
        """
        target_model = model or self.model
        system_prompt, turns = self._split_system(messages)

        try:
            response = await self._client.messages.create(
                model=target_model,
                max_tokens=8192,
                thinking={"type": "disabled"},
                system=system_prompt,
                messages=turns,
            )
        except anthropic.AnthropicError as e:
            # Callers fall back to the mock builder on any exception, so log
            # here or the real cause is lost behind a generic "[Mock]" reply.
            logger.error(f"Claude API error: {type(e).__name__}: {str(e)}")
            raise
        return "".join(block.text for block in response.content if block.type == "text")

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ):
        """
        Send a chat request to Claude and yield the assistant tokens.
        """
        target_model = model or self.model
        system_prompt, turns = self._split_system(messages)

        try:
            async with self._client.messages.stream(
                model=target_model,
                max_tokens=8192,
                thinking={"type": "disabled"},
                system=system_prompt,
                messages=turns,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"content": text}
        except anthropic.AnthropicError as e:
            logger.error(f"Claude API error: {type(e).__name__}: {str(e)}")
            raise

    def extract_prd_json(self, text: str) -> dict[str, Any]:
        """Extract the PRD JSON object from the response (see prompts module)."""
        return extract_prd_json(text)

    def build_system_prompt(self, current_prd_draft: Optional[dict[str, Any]] = None) -> str:
        """Build the strict PRD system prompt for the current draft."""
        return build_strict_prompt(current_prd_draft or {"schema_version": "0.1.0"})
