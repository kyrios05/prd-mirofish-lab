"""
services/prd_generator.py — PRD generation service.

Orchestrates incremental PRD construction using the session store and
deterministic mock builder. Each call to update_from_message():
  1. Looks up SessionState by session_id.
  2. Increments turn_count.
  3. Calls MockPRDBuilder.build_turn_delta() to get section updates.
  4. Merges new sections into current_prd_draft.
  5. Returns the updated PRDDocument (or None if session not found).

Scope guard
-----------
- Real LLM calls: separate ticket (post-T03).
- Persistence: T09 (Redis/DB backend).
- The service uses session_id (not project_id) as the primary key so the
  caller (chat route) can pass the session UUID directly.
"""

from __future__ import annotations

import re
from typing import Any, AsyncGenerator
import asyncio
import logging

from app.schemas import PRDDocument
from app.services.mock_prd_builder import build_turn_delta
from app.services.session_store import SessionState, session_store
from app.services.ollama_llm_service import OllamaLLMService
from app.config import settings

logger = logging.getLogger(__name__)

_ollama_service = OllamaLLMService()


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merges source dict into target dict.
    """
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def _strip_json_blocks(text: str) -> str:
    """
    Extracts the verbal part of an LLM response by removing JSON blocks.
    """
    # 1. Remove ```json ... ``` or ``` ... ``` blocks
    text = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", text)
    
    # 2. Remove raw JSON blocks starting with { and ending with }
    # We look for the first '{' that seems to start our schema and everything after it
    if "schema_version" in text:
        # Find the first '{' before "schema_version"
        json_start = text.find("{")
        if json_start != -1:
            text = text[:json_start]
            
    return text.strip()


class PRDGeneratorService:
    """
    Orchestrates incremental PRD document construction from chat sessions.

    Uses the module-level session_store singleton for state and the
    deterministic mock builder for section data.
    """

    # ── Public API ────────────────────────────────────────────────────────

    async def get_prd(self, session_id: str) -> dict[str, Any] | None:
        """
        Return the current PRD draft dict for a session, or None.

        The returned dict is always model_dump() output of a valid
        PRDDocument fragment (partial sections only when draft is incomplete).
        """
        state = session_store.get_session(session_id)
        if state is None:
            return None
        return state.current_prd_draft  # may be None if no turns yet

    async def update_from_message(
        self, session_id: str, message: str
    ) -> tuple[dict[str, Any] | None, str]:
        """
        Process a chat message, update the PRD draft, and return results.
        
        Attempts to use Ollama LLM if enabled, falling back to mock builder.
        """
        state: SessionState | None = session_store.get_session(session_id)
        if state is None:
            return None, "Session not found."

        # Increment turn count
        state.turn_count += 1
        
        updated_draft = state.current_prd_draft or {"schema_version": "0.1.0"}
        delta: dict[str, Any] = {}
        assistant_message: str = ""

        # 1. Try real LLM if enabled
        if settings.ollama_enabled:
            try:
                # Prepare message history for Ollama
                history = [
                    {"role": "system", "content": _ollama_service.build_system_prompt(updated_draft)}
                ]
                # Map history roles to Ollama compatible roles
                for turn in state.conversation_history:
                    history.append({"role": turn.role, "content": turn.content})
                
                # Add current user message
                history.append({"role": "user", "content": message})

                # Call Ollama
                response_text = await _ollama_service.chat(history)
                
                # Extract JSON and message
                delta = _ollama_service.extract_prd_json(response_text)
                
                # Use a more robust stripping logic for the assistant message
                assistant_message = _strip_json_blocks(response_text)
                
                if not assistant_message:
                    assistant_message = "알겠습니다. PRD 내용을 업데이트했습니다."

            except Exception as e:
                # Fallback to mock on any LLM failure
                logger.error(f"Ollama failure: {type(e).__name__} - {str(e)}")
                logger.info("Falling back to mock builder due to LLM failure.")
                delta, assistant_message = build_turn_delta(state.turn_count, session_id)
        else:
            # LLM disabled, use mock
            delta, assistant_message = build_turn_delta(state.turn_count, session_id)

        # Merge delta into current draft using deep merge to avoid data loss
        updated_draft = _deep_merge(updated_draft, delta)
        state.current_prd_draft = updated_draft

        # Record turn in conversation history
        state.add_turn(
            user_message=message,
            assistant_message=assistant_message,
        )

        # Persist updated state
        session_store.save_session(state)

        return state.current_prd_draft, assistant_message
    async def stream_update_from_message(
        self, session_id: str, message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream tokens from LLM and yield incremental updates.
        Yields dicts with 'token', 'assistant_message', or 'done' keys.
        """
        state: SessionState | None = session_store.get_session(session_id)
        if state is None:
            yield {"error": "Session not found."}
            return

        state.turn_count += 1
        updated_draft = state.current_prd_draft or {"schema_version": "0.1.0"}
        full_response = ""
        
        # 1. Try real LLM if enabled
        if settings.ollama_enabled:
            try:
                print(f"[DEBUG] Starting stream for session {session_id}", flush=True)
                yield {"status": "사용자 메시지 분석 중..."}
                history = [{"role": "system", "content": _ollama_service.build_system_prompt(updated_draft)}]
                for turn in state.conversation_history:
                    history.append({"role": turn.role, "content": turn.content})
                history.append({"role": "user", "content": message})

                # Streaming Filter State Machine
                in_code_block = False
                lookback = ""
                thinking_buffer = ""
                
                async for token_data in _ollama_service.stream_chat(history):
                    # Handle thinking tokens
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
                    
                    # Combine with lookback to detect markers split across tokens
                    current_stream = lookback + token
                    
                    if not in_code_block:
                        # 1. Detect Backticks
                        if "```" in current_stream:
                            parts = current_stream.split("```", 1)
                            text_before = parts[0]
                            if text_before.startswith(lookback):
                                text_before = text_before[len(lookback):]
                            
                            if text_before:
                                yield {"token": text_before}
                                
                            in_code_block = True
                            yield {"status": "PRD 데이터 업데이트 중..."}
                            lookback = ""
                        # 2. Detect Raw JSON Start (if LLM forgets backticks)
                        elif "{\"schema_version\"" in current_stream.replace(" ", "").replace("\n", ""):
                            # If we see {"schema_version" even without backticks, it's a JSON block
                            parts = current_stream.split("{", 1)
                            text_before = parts[0]
                            if text_before.startswith(lookback):
                                text_before = text_before[len(lookback):]
                            
                            if text_before:
                                yield {"token": text_before}
                            
                            in_code_block = True
                            yield {"status": "PRD 데이터 추출 중 (백틱 없음)..."}
                            lookback = "{" # Keep the brace for the final extraction
                        else:
                            # No markers found. Yield current token safely.
                            # We must be careful not to yield the trailing characters that might be part of a split ```
                            safe_to_yield_len = len(token)
                            if token.endswith("`"): safe_to_yield_len -= 1
                            if token.endswith("``"): safe_to_yield_len -= 2
                            
                            if safe_to_yield_len > 0:
                                yield {"token": token[:safe_to_yield_len]}
                                lookback = token[safe_to_yield_len:]
                            else:
                                lookback += token
                    else:
                        # Inside code block
                        if "```" in current_stream:
                            # Marker found, ending code block
                            in_code_block = False
                            lookback = ""
                        else:
                            # Still in code block, don't yield anything
                            lookback = token if len(token) < 3 else token[-2:]

                # After streaming is done, process JSON from the full response
                # (We use the full_response which has everything, including the hidden blocks)
                delta = _ollama_service.extract_prd_json(full_response)
                # Ensure the final assistant message shown in history is also clean
                assistant_message = _strip_json_blocks(full_response) or "알겠습니다. PRD 내용을 업데이트했습니다."
                
                updated_draft = _deep_merge(updated_draft, delta)
                state.current_prd_draft = updated_draft
                state.add_turn(user_message=message, assistant_message=assistant_message)
                session_store.save_session(state)
                
                yield {"done": True, "assistant_message": assistant_message, "current_prd_draft": updated_draft}
                return

            except Exception as e:
                logger = logging.getLogger("app.api.prd_generator")
                logger.error(f"Ollama stream failure: {str(e)}")
                # Fallback to mock below
        
        # 2. Mock Fallback (with [Mock] header)
        delta, assistant_message = build_turn_delta(state.turn_count, session_id)
        assistant_message = f"[Mock] {assistant_message}"
        
        # Simulate typing for mock
        words = assistant_message.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.05)
            yield {"token": token}
            
        updated_draft = _deep_merge(updated_draft, delta)
        state.current_prd_draft = updated_draft
        state.add_turn(user_message=message, assistant_message=assistant_message)
        session_store.save_session(state)
        
        yield {"done": True, "assistant_message": assistant_message, "current_prd_draft": updated_draft}
