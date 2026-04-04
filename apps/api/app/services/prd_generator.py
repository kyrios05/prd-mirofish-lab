"""
services/prd_generator.py — PRD generation service.

Current state: Stub service class.
Full implementation is T03 scope (LLM orchestration).

NOTE(T03): Implement incremental PRD building from chat turns.
           This service should return PRDDocument instances using
           the models defined in app.schemas.
"""

from __future__ import annotations

from app.schemas import PRDDocument


class PRDGeneratorService:
    """
    Orchestrates incremental PRD document construction from chat sessions.
    TODO(T03): Implement LLM-backed generation logic here.
    """

    async def get_prd(self, project_id: str) -> PRDDocument | None:
        """
        Retrieve the current PRD state for a project.
        TODO(T03): Load from session/storage layer.
        """
        return None

    async def update_from_message(
        self, project_id: str, message: str
    ) -> PRDDocument | None:
        """
        Update PRD based on a new chat message.
        TODO(T03): Feed message to LLM, extract structured updates,
                   apply delta to stored PRDDocument.
        """
        return None
