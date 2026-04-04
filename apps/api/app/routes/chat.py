"""
routes/chat.py — Chat-driven PRD generation endpoints.

T03 API contract (unchanged structure)
────────────────────────────────────────
POST /chat/sessions              → CreateSessionResponse
GET  /chat/sessions/{session_id} → SessionStatusResponse
POST /chat/message               → ChatResponse

T09 additions
─────────────
ChatResponse gains:
  current_phase     : str  — current ConversationPhase value
  available_actions : list[str] — actions allowed in the current phase

New endpoints:
  POST /chat/sessions/{session_id}/checkpoint  → CheckpointResponse
  POST /chat/sessions/{session_id}/restore     → RestoreResponse
  GET  /chat/sessions/{session_id}/checkpoints → CheckpointsListResponse

send_message() flow updated:
  message → phase check → update_from_message → completeness →
  auto_advance → auto-checkpoint on phase transition → response

Scope guard
-----------
- Real LLM orchestration: separate ticket.
- Markdown rendering: T04 (frozen).
- MiroFish integration: T10 (frozen).
- mock_prd_builder: T03 (frozen).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.completeness import (
    CompletenessResult,
    calculate_completeness,
    suggest_next_questions,
)
from app.services.conversation_state import (
    PHASE_GREETING_MSG,
    PHASE_READY_MSG,
    PHASE_REVIEWING_MSG,
    PHASE_VALIDATED_MSG,
    ConversationPhase,
    get_available_actions,
    list_checkpoints,
    restore_checkpoint,
    save_checkpoint,
    state_machine_from_phase,
)
from app.services.markdown_renderer import render_prd_markdown
from app.services.prd_generator import PRDGeneratorService
from app.services.session_store import session_store

router = APIRouter(prefix="/chat", tags=["chat"])

# Module-level service instance (singleton within process)
_prd_service = PRDGeneratorService()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Inbound chat message from the user."""

    session_id: str = Field(..., description="Active session UUID (from POST /chat/sessions).")
    message: str = Field(..., min_length=1, description="User's chat message text.")
    context: dict[str, Any] | None = Field(
        None,
        description="Optional extra context dict (e.g., hints from the client).",
    )


class CompletenessInfo(BaseModel):
    """Completeness snapshot of the current PRD draft."""

    filled: list[str] = Field(..., description="Section names that are present and non-empty.")
    missing: list[str] = Field(..., description="Section names that are absent or empty.")
    progress: float = Field(..., ge=0.0, le=1.0, description="Ratio of filled / total sections (0–1).")


class ChatResponse(BaseModel):
    """Response from the chat message endpoint."""

    session_id: str = Field(..., description="Echo of the session_id from the request.")
    assistant_message: str = Field(..., description="Assistant's reply text.")
    structured_prd: dict[str, Any] | None = Field(
        None,
        description="Current PRD draft as a plain dict (PRDDocument.model_dump()), or None if empty.",
    )
    prd_markdown: str | None = Field(
        None,
        description="Rendered PRD as a Markdown string (T04). None when structured_prd is None.",
    )
    draft_status: str = Field(
        ...,
        description="One of: 'empty', 'incomplete', 'ready_for_validation'.",
    )
    completeness: CompletenessInfo = Field(..., description="Section completeness breakdown.")
    next_questions: list[str] = Field(
        default_factory=list,
        description="Suggested next questions for missing sections (max 3).",
    )
    # T09 additions -----------------------------------------------------------
    current_phase: str = Field(
        default=ConversationPhase.GREETING.value,
        description="Current conversation phase (T09).",
    )
    available_actions: list[str] = Field(
        default_factory=list,
        description="Actions available in the current phase (T09).",
    )


class CreateSessionResponse(BaseModel):
    """Response from POST /chat/sessions."""

    session_id: str = Field(..., description="Newly created session UUID.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    message: str = Field(..., description="Welcome message.")


class SessionStatusResponse(BaseModel):
    """Response from GET /chat/sessions/{session_id}."""

    session_id: str
    created_at: str
    turn_count: int
    has_prd_draft: bool
    draft_status: str
    completeness: CompletenessInfo
    conversation_history: list[dict[str, Any]]


# T09 checkpoint response models ----------------------------------------------

class CheckpointResponse(BaseModel):
    """Response from POST /chat/sessions/{session_id}/checkpoint."""

    checkpoint_id: str = Field(..., description="UUID of the created checkpoint.")
    label: str = Field(..., description="Human-readable checkpoint label.")
    phase: str = Field(..., description="Phase at which the checkpoint was saved.")
    turn_count: int = Field(..., description="Turn count at checkpoint.")


class RestoreRequest(BaseModel):
    """Request body for POST /chat/sessions/{session_id}/restore."""

    checkpoint_id: str = Field(..., description="ID of the checkpoint to restore.")


class RestoreResponse(BaseModel):
    """Response from POST /chat/sessions/{session_id}/restore."""

    restored: bool = Field(..., description="True if restore succeeded.")
    checkpoint_id: str = Field(..., description="Checkpoint ID that was restored.")
    current_phase: str = Field(..., description="Phase after restore.")
    turn_count: int = Field(..., description="Turn count after restore.")
    prd_draft_present: bool = Field(..., description="Whether PRD draft is present after restore.")


class CheckpointsListResponse(BaseModel):
    """Response from GET /chat/sessions/{session_id}/checkpoints."""

    session_id: str
    checkpoints: list[dict[str, Any]]   # Checkpoint.to_dict() each


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _completeness_from_result(result: CompletenessResult) -> CompletenessInfo:
    return CompletenessInfo(
        filled=result.filled,
        missing=result.missing,
        progress=round(result.progress, 4),
    )


def _phase_assistant_message(phase: ConversationPhase, base_message: str) -> str:
    """
    Prepend or append a phase-transition notice to the assistant message when
    the phase has semantic importance.

    INTERVIEWING:       use base_message (mock_prd_builder message)
    REVIEWING:          override with the reviewing prompt
    READY_FOR_VALIDATION: override with the ready prompt
    VALIDATED:          override with the validated prompt
    """
    if phase == ConversationPhase.REVIEWING:
        return PHASE_REVIEWING_MSG
    if phase == ConversationPhase.READY_FOR_VALIDATION:
        return PHASE_READY_MSG
    if phase == ConversationPhase.VALIDATED:
        return PHASE_VALIDATED_MSG
    return base_message


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session() -> CreateSessionResponse:
    """
    Create a new chat session and return its session_id.

    The returned session_id must be passed in subsequent POST /chat/message calls.
    """
    state = session_store.create_session()
    return CreateSessionResponse(
        session_id=state.session_id,
        created_at=state.created_at,
        message="새 세션이 생성되었습니다. 제품 아이디어를 채팅으로 알려주세요!",
    )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """
    Return the current status and conversation history of a session.

    Raises 404 if the session does not exist.
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    completeness = calculate_completeness(state.current_prd_draft)

    return SessionStatusResponse(
        session_id=state.session_id,
        created_at=state.created_at,
        turn_count=state.turn_count,
        has_prd_draft=state.current_prd_draft is not None,
        draft_status=completeness.draft_status,
        completeness=_completeness_from_result(completeness),
        conversation_history=[
            {"role": t.role, "content": t.content, "timestamp": t.timestamp}
            for t in state.conversation_history
        ],
    )


@router.post("/message", response_model=ChatResponse)
async def send_message(body: ChatRequest) -> ChatResponse:
    """
    Process a user chat message and return the updated PRD draft.

    T09 flow
    --------
    1. Validate session exists (404 if not).
    2. Phase-aware pre-processing:
       - GREETING → transition to INTERVIEWING on first user message.
    3. Call PRDGeneratorService.update_from_message() to advance the mock draft.
    4. Calculate completeness.
    5. auto_advance: check INTERVIEWING → REVIEWING when progress == 1.0.
    6. Auto-checkpoint when phase transitions.
    7. Persist updated state.
    8. Return ChatResponse with current_phase, available_actions + existing fields.
    """
    # 1. Validate session
    state = session_store.get_session(body.session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{body.session_id}' not found. "
                   "Create a session first via POST /chat/sessions.",
        )

    # 2. Reconstruct state machine from persisted phase
    sm = state_machine_from_phase(state.current_phase)
    phase_transitioned = False

    # GREETING → INTERVIEWING on first user message
    if sm.current_phase == ConversationPhase.GREETING:
        transitioned = sm.transition(
            ConversationPhase.INTERVIEWING,
            trigger="user_first_message",
            phase_history=state.phase_history,
        )
        if transitioned:
            state.current_phase = sm.current_phase.value
            phase_transitioned = True

    # 3. Update PRD draft via service
    updated_draft, assistant_message = await _prd_service.update_from_message(
        session_id=body.session_id,
        message=body.message,
    )

    # 4. Calculate completeness
    completeness = calculate_completeness(updated_draft)
    next_questions = suggest_next_questions(completeness.missing, max_count=3)

    # 5. auto_advance: INTERVIEWING → REVIEWING when complete
    advanced_phase = sm.auto_advance(
        completeness=completeness,
        phase_history=state.phase_history,
    )
    if advanced_phase is not None:
        state.current_phase = sm.current_phase.value
        phase_transitioned = True

    # 6. Auto-checkpoint on phase transition
    if phase_transitioned:
        label = (
            f"Turn {state.turn_count} - auto checkpoint "
            f"(→ {state.current_phase})"
        )
        save_checkpoint(state, label=label)

    # Persist state (session_store already updated by prd_service, but
    # we need to save the phase / checkpoint updates)
    session_store.save_session(state)

    # 7. Phase-specific assistant message override
    current_phase_enum = ConversationPhase(state.current_phase)
    final_message = _phase_assistant_message(current_phase_enum, assistant_message)

    # 8. Render Markdown (T04)
    prd_markdown = render_prd_markdown(updated_draft) if updated_draft else None

    # 9. Build response
    return ChatResponse(
        session_id=body.session_id,
        assistant_message=final_message,
        structured_prd=updated_draft,
        prd_markdown=prd_markdown,
        draft_status=completeness.draft_status,
        completeness=_completeness_from_result(completeness),
        next_questions=next_questions,
        current_phase=state.current_phase,
        available_actions=get_available_actions(current_phase_enum),
    )


# ---------------------------------------------------------------------------
# T09 Checkpoint endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/checkpoint",
    response_model=CheckpointResponse,
    status_code=200,
)
async def create_checkpoint(
    session_id: str,
    label: str | None = None,
) -> CheckpointResponse:
    """
    Manually create a checkpoint for the session's current state.

    Parameters
    ----------
    label : Optional human-readable label. Defaults to
            "Turn {n} - manual checkpoint".
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    effective_label = label or f"Turn {state.turn_count} - manual checkpoint"
    checkpoint = save_checkpoint(state, label=effective_label)
    session_store.save_session(state)

    return CheckpointResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        label=checkpoint.label,
        phase=checkpoint.phase,
        turn_count=checkpoint.turn_count,
    )


@router.post(
    "/sessions/{session_id}/restore",
    response_model=RestoreResponse,
    status_code=200,
)
async def restore_from_checkpoint(
    session_id: str,
    body: RestoreRequest,
) -> RestoreResponse:
    """
    Restore a session's PRD draft, turn_count, and phase to a saved checkpoint.

    conversation_history is preserved so the user retains dialogue context.
    Returns 404 if the session or checkpoint is not found.
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    success = restore_checkpoint(state, body.checkpoint_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint '{body.checkpoint_id}' not found in session '{session_id}'.",
        )

    session_store.save_session(state)

    return RestoreResponse(
        restored=True,
        checkpoint_id=body.checkpoint_id,
        current_phase=state.current_phase,
        turn_count=state.turn_count,
        prd_draft_present=state.current_prd_draft is not None,
    )


@router.get(
    "/sessions/{session_id}/checkpoints",
    response_model=CheckpointsListResponse,
    status_code=200,
)
async def get_checkpoints(session_id: str) -> CheckpointsListResponse:
    """
    Return all checkpoints for a session, sorted newest-first.
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    sorted_checkpoints = list_checkpoints(state)

    return CheckpointsListResponse(
        session_id=session_id,
        checkpoints=[c.to_dict() for c in sorted_checkpoints],
    )
