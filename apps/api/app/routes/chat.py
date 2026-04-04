"""
routes/chat.py — Chat-driven PRD generation endpoints.

New API contract (T03)
──────────────────────
POST /chat/sessions              → CreateSessionResponse
GET  /chat/sessions/{session_id} → SessionStatusResponse
POST /chat/message               → ChatResponse

ChatRequest  : session_id, message, context (optional)
ChatResponse : session_id, assistant_message, structured_prd (dict|None),
               draft_status, completeness (CompletenessInfo), next_questions

Scope guard
-----------
- Real LLM orchestration: separate ticket.
- Markdown rendering: T04.
- MiroFish integration: T10.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.completeness import CompletenessResult, calculate_completeness, suggest_next_questions
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
    draft_status: str = Field(
        ...,
        description="One of: 'empty', 'incomplete', 'ready_for_validation'.",
    )
    completeness: CompletenessInfo = Field(..., description="Section completeness breakdown.")
    next_questions: list[str] = Field(
        default_factory=list,
        description="Suggested next questions for missing sections (max 3).",
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _completeness_from_result(result: CompletenessResult) -> CompletenessInfo:
    return CompletenessInfo(
        filled=result.filled,
        missing=result.missing,
        progress=round(result.progress, 4),
    )


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

    Flow
    ----
    1. Validate session exists (404 if not).
    2. Call PRDGeneratorService.update_from_message() to advance the mock draft.
    3. Calculate completeness.
    4. Return ChatResponse with structured_prd, draft_status, completeness, next_questions.
    """
    # 1. Validate session
    state = session_store.get_session(body.session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{body.session_id}' not found. "
                   "Create a session first via POST /chat/sessions.",
        )

    # 2. Update PRD draft via service
    updated_draft, assistant_message = await _prd_service.update_from_message(
        session_id=body.session_id,
        message=body.message,
    )

    # 3. Calculate completeness
    completeness = calculate_completeness(updated_draft)
    next_questions = suggest_next_questions(completeness.missing, max_count=3)

    # 4. Build response
    return ChatResponse(
        session_id=body.session_id,
        assistant_message=assistant_message,
        structured_prd=updated_draft,
        draft_status=completeness.draft_status,
        completeness=_completeness_from_result(completeness),
        next_questions=next_questions,
    )
