"""
services/session_store.py — In-memory session state store.

Stores conversation history and the current PRD draft for each chat session.
The store is a module-level singleton (plain dict) — no persistence.

Scope guard
-----------
- State machine / checkpointing: T09
- Persistence (Redis/DB): separate infra ticket
- LLM history compression: separate ticket
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------
@dataclass
class ConversationTurn:
    """A single exchange in the chat history."""
    role: str          # "user" | "assistant"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SessionState:
    """
    Full state of a chat session.

    Attributes
    ----------
    session_id:          Unique identifier for the session.
    created_at:          ISO-8601 creation timestamp.
    turn_count:          Number of user messages received so far.
    conversation_history: Ordered list of ConversationTurn objects.
    current_prd_draft:   Latest partial PRD as a plain dict (model_dump output),
                         or None if no turns have been processed yet.
                         This is always the output of PRDDocument.model_dump()
                         when present, making it T02-validatable.
    project_id:          Derived from session_id for use in service calls.
    """

    session_id: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    turn_count: int = 0
    conversation_history: list[ConversationTurn] = field(default_factory=list)
    current_prd_draft: dict[str, Any] | None = None

    @property
    def project_id(self) -> str:
        return f"proj-{self.session_id[:8]}"

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        """Append a user+assistant exchange and increment turn counter."""
        self.conversation_history.append(
            ConversationTurn(role="user", content=user_message)
        )
        self.conversation_history.append(
            ConversationTurn(role="assistant", content=assistant_message)
        )
        self.turn_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "turn_count": self.turn_count,
            "has_prd_draft": self.current_prd_draft is not None,
            "conversation_history": [
                {"role": t.role, "content": t.content, "timestamp": t.timestamp}
                for t in self.conversation_history
            ],
        }


# ---------------------------------------------------------------------------
# SessionStore — module-level singleton
# ---------------------------------------------------------------------------
class SessionStore:
    """
    Thread-safe-enough in-memory session store backed by a plain dict.

    FastAPI runs on asyncio (single-threaded event loop), so no explicit
    locking is needed for the in-memory dict.

    NOTE(T09): Replace with a proper state machine and persistent backend.
    """

    def __init__(self) -> None:
        self._store: dict[str, SessionState] = {}

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create_session(self) -> SessionState:
        """Create and register a new session, returning the SessionState."""
        session_id = str(uuid.uuid4())
        state = SessionState(session_id=session_id)
        self._store[session_id] = state
        return state

    def get_session(self, session_id: str) -> SessionState | None:
        """Return SessionState or None if not found."""
        return self._store.get(session_id)

    def save_session(self, state: SessionState) -> None:
        """Persist (overwrite) a session state object."""
        self._store[state.session_id] = state

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    # ── Helpers ─────────────────────────────────────────────────────────────

    def session_count(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        """Wipe all sessions — useful for tests."""
        self._store.clear()


# ---------------------------------------------------------------------------
# Module-level singleton — shared across the process
# ---------------------------------------------------------------------------
session_store = SessionStore()
