"""
services/conversation_state.py — Explicit conversation state machine and
checkpoint service for PRD generation sessions.

Implements T09: ConversationPhase enum, ConversationStateMachine with guard-
protected transitions, Checkpoint / PhaseTransition dataclasses, and pure
functions for checkpoint management.

Dependency chain (AGENTS.md import rules)
------------------------------------------
  conversation_state → completeness (CompletenessResult only)
  session_store      → conversation_state  (SessionState extended in T09)
  routes/chat        → conversation_state, session_store

Scope guard
-----------
- Real LLM orchestration: separate ticket
- Persistence (Redis/DB): separate infra ticket
- MiroFish HTTP call: T10
- mock_prd_builder, markdown_renderer, validation_packager: frozen (T03/T04/T05)
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from app.services.completeness import CompletenessResult

if TYPE_CHECKING:
    # Avoid circular import at runtime; only used in type hints
    pass


# ---------------------------------------------------------------------------
# ConversationPhase enum
# ---------------------------------------------------------------------------

class ConversationPhase(str, Enum):
    """
    Explicit phases of the PRD generation conversation.

    str+Enum ensures JSON serialisation works without custom encoders:
        json.dumps(ConversationPhase.GREETING)   → '"greeting"'
        ConversationPhase("greeting")             → ConversationPhase.GREETING
    """
    GREETING = "greeting"
    INTERVIEWING = "interviewing"
    REVIEWING = "reviewing"
    READY_FOR_VALIDATION = "ready_for_validation"
    VALIDATED = "validated"


# ---------------------------------------------------------------------------
# Phase-level metadata helpers
# ---------------------------------------------------------------------------

#: Actions available in each phase (shown to the client in ChatResponse)
PHASE_AVAILABLE_ACTIONS: dict[str, list[str]] = {
    ConversationPhase.GREETING: [
        "introduce_product",
    ],
    ConversationPhase.INTERVIEWING: [
        "continue",
        "skip_section",
        "save_checkpoint",
    ],
    ConversationPhase.REVIEWING: [
        "confirm",
        "edit_section",
        "restart_section",
        "save_checkpoint",
    ],
    ConversationPhase.READY_FOR_VALIDATION: [
        "run_validation",
        "go_back",
    ],
    ConversationPhase.VALIDATED: [
        "view_result",
        "edit_section",
        "restart_section",
    ],
}

#: Default assistant messages for each phase transition
PHASE_GREETING_MSG = (
    "안녕하세요! 어떤 제품의 PRD를 작성할까요? "
    "제품 이름과 한 줄 설명을 알려주세요."
)
PHASE_REVIEWING_MSG = (
    "PRD 초안이 완성되었습니다! 수정할 부분이 있으면 말씀해주세요. "
    "없으면 '검증 시작'이라고 해주세요."
)
PHASE_READY_MSG = (
    "검증을 시작할 준비가 되었습니다. "
    "/validation/run을 호출하거나 '검증 실행'이라고 말씀해주세요."
)
PHASE_VALIDATED_MSG = (
    "검증이 완료되었습니다. 결과를 검토하고 수정이 필요하면 말씀해주세요."
)


def get_available_actions(phase: ConversationPhase) -> list[str]:
    """Return the list of available action strings for the given phase."""
    return list(PHASE_AVAILABLE_ACTIONS.get(phase, []))


# ---------------------------------------------------------------------------
# Checkpoint dataclass
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """
    A snapshot of PRD draft state at a particular conversation moment.

    prd_snapshot is a deep copy of current_prd_draft — never shares
    references with the live draft.
    """
    checkpoint_id: str
    created_at: str
    phase: str                          # ConversationPhase.value
    turn_count: int
    prd_snapshot: dict                  # deep copy of current_prd_draft
    label: str                          # human-readable description

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "phase": self.phase,
            "turn_count": self.turn_count,
            "prd_snapshot": self.prd_snapshot,
            "label": self.label,
        }


# ---------------------------------------------------------------------------
# PhaseTransition dataclass
# ---------------------------------------------------------------------------

@dataclass
class PhaseTransition:
    """
    Records a single phase transition event in the session history.
    """
    from_phase: str
    to_phase: str
    trigger: str       # e.g. "auto_advance", "user_request", "validation_complete"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "from_phase": self.from_phase,
            "to_phase": self.to_phase,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# ConversationStateMachine
# ---------------------------------------------------------------------------

# Allowed transitions: (from_phase, to_phase)
_ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    (ConversationPhase.GREETING,             ConversationPhase.INTERVIEWING),
    (ConversationPhase.INTERVIEWING,         ConversationPhase.REVIEWING),
    (ConversationPhase.REVIEWING,            ConversationPhase.INTERVIEWING),
    (ConversationPhase.REVIEWING,            ConversationPhase.READY_FOR_VALIDATION),
    (ConversationPhase.READY_FOR_VALIDATION, ConversationPhase.VALIDATED),
    (ConversationPhase.VALIDATED,            ConversationPhase.REVIEWING),
}


class ConversationStateMachine:
    """
    Lightweight state machine for the PRD generation conversation.

    The machine holds the *current_phase* and validates transitions before
    executing them.  It does not own SessionState; the caller is responsible
    for passing ``state`` objects to methods that need to record history.

    Usage
    -----
    >>> from app.services.conversation_state import (
    ...     ConversationPhase, ConversationStateMachine
    ... )
    >>> sm = ConversationStateMachine()
    >>> sm.current_phase
    <ConversationPhase.GREETING: 'greeting'>
    >>> sm.transition(ConversationPhase.INTERVIEWING, trigger="user_first_message")
    True
    """

    def __init__(
        self,
        initial_phase: ConversationPhase = ConversationPhase.GREETING,
    ) -> None:
        self.current_phase: ConversationPhase = initial_phase

    # ── Guard ────────────────────────────────────────────────────────────────

    def can_transition(
        self,
        target: ConversationPhase,
        completeness: CompletenessResult | None = None,
    ) -> bool:
        """
        Return True if the transition to *target* is allowed from the
        current phase (including optional guard conditions).

        Guard conditions
        ----------------
        INTERVIEWING → REVIEWING  requires  completeness.progress == 1.0
        All other allowed transitions have no additional guards.

        Returns False (never raises) for disallowed / unknown transitions.
        """
        key = (self.current_phase, target)
        if key not in _ALLOWED_TRANSITIONS:
            return False

        # Extra guard: INTERVIEWING → REVIEWING only when PRD is complete
        if (
            self.current_phase == ConversationPhase.INTERVIEWING
            and target == ConversationPhase.REVIEWING
        ):
            if completeness is None or completeness.progress < 1.0:
                return False

        return True

    # ── Execute ──────────────────────────────────────────────────────────────

    def transition(
        self,
        target: ConversationPhase,
        trigger: str = "user_request",
        completeness: CompletenessResult | None = None,
        phase_history: list[PhaseTransition] | None = None,
    ) -> bool:
        """
        Attempt a transition to *target*.

        Parameters
        ----------
        target        : Desired next phase.
        trigger       : Human-readable cause (e.g. "auto_advance").
        completeness  : Required when transitioning INTERVIEWING → REVIEWING.
        phase_history : If provided, append a PhaseTransition record on success.

        Returns
        -------
        True  if the transition was executed.
        False if the transition was rejected (not an error).
        """
        if not self.can_transition(target, completeness=completeness):
            return False

        record = PhaseTransition(
            from_phase=self.current_phase.value,
            to_phase=target.value,
            trigger=trigger,
        )

        self.current_phase = target

        if phase_history is not None:
            phase_history.append(record)

        return True

    # ── Auto-advance ─────────────────────────────────────────────────────────

    def auto_advance(
        self,
        completeness: CompletenessResult,
        phase_history: list[PhaseTransition] | None = None,
    ) -> ConversationPhase | None:
        """
        Check whether the current state should automatically advance based on
        the completeness result, and execute the transition if so.

        Rules
        -----
        - GREETING:      never auto-advances (requires explicit user message).
        - INTERVIEWING:  advance to REVIEWING when progress == 1.0.
        - Other phases:  no automatic advancement.

        Returns the *new* phase if a transition occurred, else None.
        """
        if (
            self.current_phase == ConversationPhase.INTERVIEWING
            and completeness.progress >= 1.0
        ):
            success = self.transition(
                ConversationPhase.REVIEWING,
                trigger="auto_advance",
                completeness=completeness,
                phase_history=phase_history,
            )
            return self.current_phase if success else None

        return None


# ---------------------------------------------------------------------------
# Checkpoint service functions
# ---------------------------------------------------------------------------

def save_checkpoint(
    state: "SessionStateProtocol",
    label: str,
) -> Checkpoint:
    """
    Create a checkpoint from the current session state and append it.

    A deep copy of ``state.current_prd_draft`` is stored to prevent
    subsequent mutations from affecting the snapshot.

    Parameters
    ----------
    state : SessionState-compatible object (duck-typed)
    label : Human-readable description, e.g. "Turn 3 - users+problem 완성 후"

    Returns
    -------
    The newly created Checkpoint (also appended to state.checkpoints).
    """
    snapshot = copy.deepcopy(state.current_prd_draft or {})
    checkpoint = Checkpoint(
        checkpoint_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        phase=state.current_phase,
        turn_count=state.turn_count,
        prd_snapshot=snapshot,
        label=label,
    )
    state.checkpoints.append(checkpoint)
    return checkpoint


def restore_checkpoint(
    state: "SessionStateProtocol",
    checkpoint_id: str,
) -> bool:
    """
    Restore PRD draft, turn_count, and phase from a saved checkpoint.

    conversation_history is intentionally preserved so the user retains
    the full dialogue context.

    Returns True on success, False if checkpoint_id is not found.
    """
    target: Checkpoint | None = next(
        (c for c in state.checkpoints if c.checkpoint_id == checkpoint_id),
        None,
    )
    if target is None:
        return False

    state.current_prd_draft = copy.deepcopy(target.prd_snapshot) or None
    state.turn_count = target.turn_count
    state.current_phase = target.phase   # string value stored in SessionState
    return True


def list_checkpoints(state: "SessionStateProtocol") -> list[Checkpoint]:
    """
    Return the checkpoints list sorted newest-first (by created_at DESC).
    """
    return sorted(
        state.checkpoints,
        key=lambda c: c.created_at,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Helper: build ConversationStateMachine from a SessionState's current phase
# ---------------------------------------------------------------------------

def state_machine_from_phase(phase_str: str) -> ConversationStateMachine:
    """
    Reconstruct a ConversationStateMachine from a persisted phase string.

    Falls back to GREETING if the value is unrecognised.
    """
    try:
        phase = ConversationPhase(phase_str)
    except ValueError:
        phase = ConversationPhase.GREETING
    return ConversationStateMachine(initial_phase=phase)
