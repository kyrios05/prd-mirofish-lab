"""
routes/chat.py — Chat-driven PRD generation endpoint.

Current state: Placeholder router with stub endpoints.
The actual chat orchestration logic is T03 scope.

NOTE(T03): Wire up prd_generator.py service here and update
           request/response models to use PRDDocument from app.schemas.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Inbound chat message from user."""

    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Chat response — stub until T03."""

    session_id: str
    reply: str
    prd_updated: bool = False


@router.post("/message", response_model=ChatResponse)
async def send_message(body: ChatMessage) -> ChatResponse:
    """
    Process a chat message and optionally update the in-progress PRD.
    TODO(T03): Implement LLM orchestration and PRD update logic.
    """
    return ChatResponse(
        session_id=body.session_id,
        reply="[T03 stub] Chat orchestration not yet implemented.",
        prd_updated=False,
    )
