"""
services/openai_llm_service.py — Service for interacting with the OpenAI API.

Drop-in replacement for OllamaLLMService / ClaudeLLMService (same chat/
stream_chat/extract_prd_json/build_system_prompt interface) backed by
OpenAI's hosted GPT models via the Responses API.
"""

import logging
from typing import Any, Optional

import openai
from app.config import settings
from app.services.prompts import build_system_prompt as build_strict_prompt
from app.services.prompts import extract_prd_json

logger = logging.getLogger("app.api.openai")


class OpenAILLMService:
    """
    Service for interacting with the OpenAI API to facilitate
    chat-driven PRD generation and stakeholder proposal generation.
    """

    def __init__(self):
        # Strip whitespace — .env values often have a leading space after '='.
        self.model = (settings.openai_model or "").strip()
        self._client = openai.AsyncOpenAI(
            api_key=(settings.openai_api_key or "").strip() or None,
            timeout=settings.llm_timeout,
        )

    @staticmethod
    def _split_system(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
        """
        The Responses API takes the system prompt as a separate top-level
        'instructions' parameter rather than a message with role='system'.
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
        Send a chat request to OpenAI and return the assistant message content.
        """
        target_model = model or self.model
        instructions, turns = self._split_system(messages)

        try:
            response = await self._client.responses.create(
                model=target_model,
                instructions=instructions,
                input=turns,
                reasoning={"effort": settings.openai_reasoning_effort},
            )
        except openai.OpenAIError as e:
            # Callers fall back to the mock builder on any exception, so log
            # here or the real cause is lost behind a generic "[Mock]" reply.
            logger.error(f"OpenAI API error: {type(e).__name__}: {str(e)}")
            raise
        return response.output_text

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
    ):
        """
        Send a chat request to OpenAI and yield the assistant tokens.
        """
        target_model = model or self.model
        instructions, turns = self._split_system(messages)

        try:
            stream = await self._client.responses.create(
                model=target_model,
                instructions=instructions,
                input=turns,
                reasoning={"effort": settings.openai_reasoning_effort},
                stream=True,
            )
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield {"content": event.delta}
        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error: {type(e).__name__}: {str(e)}")
            raise

    def extract_prd_json(self, text: str) -> dict[str, Any]:
        """Extract the PRD JSON object from the response (see prompts module)."""
        return extract_prd_json(text)

    def build_system_prompt(self, current_prd_draft: Optional[dict[str, Any]] = None) -> str:
        """Build the strict PRD system prompt for the current draft."""
        return build_strict_prompt(current_prd_draft or {"schema_version": "0.1.0"})
