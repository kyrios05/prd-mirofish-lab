"""
services/prd_generator.py — PRD generation service.

Orchestrates incremental PRD construction using the session store and
the configured LLM provider (OpenAI / Claude / Ollama). Falls back to the
deterministic mock builder only when LLM is explicitly disabled.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncGenerator

from app.config import settings
from app.services.llm_provider import get_llm_service
from app.services.mock_prd_builder import build_turn_delta
from app.services.prompts import is_greeting_only
from app.services.session_store import SessionState, session_store

logger = logging.getLogger(__name__)


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Recursively merges source dict into target dict."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def _strip_json_blocks(text: str) -> str:
    """Extract the verbal part of an LLM response by removing JSON blocks."""
    text = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", text)

    if "schema_version" in text:
        json_start = text.find("{")
        if json_start != -1:
            text = text[:json_start]

    return text.strip()


def _llm_failure_message(exc: Exception) -> str:
    error_text = str(exc).lower()

    if "quota" in error_text or "billing" in error_text:
        return (
            "LLM API 사용 한도에 도달했거나 결제 설정이 필요합니다. "
            "Live ON에서는 PRD 초안을 변경하지 않았습니다. "
            "OpenAI 사용 한도와 결제 상태를 확인한 뒤 다시 시도해주세요."
        )

    if "api key" in error_text or "authentication" in error_text:
        return (
            "LLM API 인증에 실패했습니다. Live ON에서는 PRD 초안을 변경하지 않았습니다. "
            "API 키와 제공자 설정을 확인한 뒤 다시 시도해주세요."
        )

    return (
        f"{settings.llm_provider} LLM 호출에 실패했습니다. "
        "Live ON에서는 PRD 초안을 변경하지 않았습니다. "
        "API 연결과 모델 설정을 확인한 뒤 다시 시도해주세요."
    )


class PRDGeneratorService:
    """Orchestrates incremental PRD document construction from chat sessions."""

    async def get_prd(self, session_id: str) -> dict[str, Any] | None:
        """Return the current PRD draft dict for a session, or None."""
        state = session_store.get_session(session_id)
        if state is None:
            return None
        return state.current_prd_draft

    async def update_from_message(
        self, session_id: str, message: str, *, use_llm: bool | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        """
        Process a chat message, update the PRD draft, and return results.

        use_llm:
          True  → call configured LLM; on failure leave PRD unchanged (no mock).
          False → deterministic mock builder (Live OFF).
          None  → follow settings.ollama_enabled.
        """
        state: SessionState | None = session_store.get_session(session_id)
        if state is None:
            return None, "Session not found."

        # turn_count is incremented inside state.add_turn(); compute upcoming turn here.
        next_turn = state.turn_count + 1
        updated_draft = state.current_prd_draft or {"schema_version": "0.1.0"}
        delta: dict[str, Any] = {}
        assistant_message = ""

        llm_on = settings.ollama_enabled if use_llm is None else bool(use_llm)
        if llm_on:
            try:
                history = [
                    {
                        "role": "system",
                        "content": get_llm_service().build_system_prompt(updated_draft),
                    }
                ]
                for turn in state.conversation_history:
                    history.append({"role": turn.role, "content": turn.content})
                history.append({"role": "user", "content": message})

                response_text = await get_llm_service().chat(history)
                delta = get_llm_service().extract_prd_json(response_text)
                if is_greeting_only(message):
                    delta = {}
                assistant_message = _strip_json_blocks(response_text) or (
                    "Understood. Updated the PRD draft."
                )
            except Exception as e:
                logger.error(
                    "LLM failure (provider=%s): %s - %s",
                    settings.llm_provider,
                    type(e).__name__,
                    e,
                )
                assistant_message = _llm_failure_message(e)
                state.add_turn(user_message=message, assistant_message=assistant_message)
                session_store.save_session(state)
                return state.current_prd_draft, assistant_message
        else:
            delta, assistant_message = build_turn_delta(next_turn, session_id)

        updated_draft = _deep_merge(updated_draft, delta)
        state.current_prd_draft = updated_draft
        state.add_turn(user_message=message, assistant_message=assistant_message)
        session_store.save_session(state)
        return state.current_prd_draft, assistant_message

    async def stream_update_from_message(
        self, session_id: str, message: str, *, use_llm: bool | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream tokens from LLM and yield incremental updates."""
        state: SessionState | None = session_store.get_session(session_id)
        if state is None:
            yield {"error": "Session not found."}
            return

        next_turn = state.turn_count + 1
        updated_draft = state.current_prd_draft or {"schema_version": "0.1.0"}
        full_response = ""

        llm_on = settings.ollama_enabled if use_llm is None else bool(use_llm)
        if llm_on:
            try:
                yield {"status": "Analyzing message..."}
                history = [
                    {
                        "role": "system",
                        "content": get_llm_service().build_system_prompt(updated_draft),
                    }
                ]
                for turn in state.conversation_history:
                    history.append({"role": turn.role, "content": turn.content})
                history.append({"role": "user", "content": message})

                in_code_block = False
                lookback = ""
                thinking_buffer = ""

                async for token_data in get_llm_service().stream_chat(history):
                    if "thinking" in token_data:
                        thinking_token = token_data["thinking"]
                        thinking_buffer += thinking_token
                        if len(thinking_buffer) > 20 or "\n" in thinking_token:
                            yield {"status": f"Thinking... {thinking_buffer.strip()}"}
                            thinking_buffer = thinking_buffer[-20:]
                        continue

                    if thinking_buffer:
                        yield {"status": "Thinking complete. Generating response..."}
                        thinking_buffer = ""

                    token = token_data.get("content", "")
                    if not token:
                        continue

                    full_response += token
                    current_stream = lookback + token

                    if not in_code_block:
                        if "```" in current_stream:
                            parts = current_stream.split("```", 1)
                            text_before = parts[0]
                            if text_before.startswith(lookback):
                                text_before = text_before[len(lookback) :]
                            if text_before:
                                yield {"token": text_before}
                            in_code_block = True
                            yield {"status": "Updating PRD data..."}
                            lookback = ""
                        elif '{"schema_version"' in current_stream.replace(" ", "").replace(
                            "\n", ""
                        ):
                            parts = current_stream.split("{", 1)
                            text_before = parts[0]
                            if text_before.startswith(lookback):
                                text_before = text_before[len(lookback) :]
                            if text_before:
                                yield {"token": text_before}
                            in_code_block = True
                            yield {"status": "Extracting PRD JSON..."}
                            lookback = "{"
                        else:
                            safe_to_yield_len = len(token)
                            if token.endswith("`"):
                                safe_to_yield_len -= 1
                            if token.endswith("``"):
                                safe_to_yield_len -= 2

                            if safe_to_yield_len > 0:
                                yield {"token": token[:safe_to_yield_len]}
                                lookback = token[safe_to_yield_len:]
                            else:
                                lookback += token
                    else:
                        if "```" in current_stream:
                            in_code_block = False
                            lookback = ""
                        else:
                            lookback = token if len(token) < 3 else token[-2:]

                delta = get_llm_service().extract_prd_json(full_response)
                if is_greeting_only(message):
                    delta = {}
                assistant_message = _strip_json_blocks(full_response) or (
                    "Understood. Updated the PRD draft."
                )

                updated_draft = _deep_merge(updated_draft, delta)
                state.current_prd_draft = updated_draft
                state.add_turn(user_message=message, assistant_message=assistant_message)
                session_store.save_session(state)

                yield {
                    "done": True,
                    "assistant_message": assistant_message,
                    "current_prd_draft": updated_draft,
                }
                return

            except Exception as e:
                logger.error(
                    "LLM stream failure (provider=%s): %s - %s",
                    settings.llm_provider,
                    type(e).__name__,
                    e,
                )
                err_msg = _llm_failure_message(e)
                state.add_turn(user_message=message, assistant_message=err_msg)
                session_store.save_session(state)
                yield {"token": err_msg}
                yield {
                    "done": True,
                    "assistant_message": err_msg,
                    "current_prd_draft": updated_draft,
                }
                return

        # Intentional mock path (LLM disabled via ollama_enabled=False)
        delta, assistant_message = build_turn_delta(next_turn, session_id)
        assistant_message = f"[Mock] {assistant_message}"

        words = assistant_message.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.05)
            yield {"token": token}

        updated_draft = _deep_merge(updated_draft, delta)
        state.current_prd_draft = updated_draft
        state.add_turn(user_message=message, assistant_message=assistant_message)
        session_store.save_session(state)

        yield {
            "done": True,
            "assistant_message": assistant_message,
            "current_prd_draft": updated_draft,
        }
