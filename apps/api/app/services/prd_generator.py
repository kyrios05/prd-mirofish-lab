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

from typing import Any

from app.schemas import PRDDocument
from app.services.mock_prd_builder import build_turn_delta
from app.services.session_store import SessionState, session_store


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

        Parameters
        ----------
        session_id : str   Active session UUID.
        message    : str   Raw user message (unused in mock; real LLM uses it).

        Returns
        -------
        (updated_draft, assistant_message)
        updated_draft    – Merged PRD draft dict (partial or complete) or None
                           if the session does not exist.
        assistant_message – Human-readable assistant reply for this turn.
        """
        state: SessionState | None = session_store.get_session(session_id)
        if state is None:
            return None, "Session not found."

        # Increment turn and get deterministic delta
        next_turn = state.turn_count + 1
        delta, assistant_message = build_turn_delta(next_turn, session_id)

        # Merge delta into current draft
        if state.current_prd_draft is None:
            # First turn: start from a minimal skeleton with schema_version
            state.current_prd_draft = {"schema_version": "0.1.0"}

        state.current_prd_draft.update(delta)

        # Record turn in conversation history
        state.add_turn(
            user_message=message,
            assistant_message=assistant_message,
        )

        # Persist updated state
        session_store.save_session(state)

        return state.current_prd_draft, assistant_message
