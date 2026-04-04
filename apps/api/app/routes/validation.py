"""
routes/validation.py — PRD validation trigger endpoint.

Current state: Placeholder router with stub endpoints.
Actual validation packaging + MiroFish invocation is T05 scope.

NOTE(T05): Replace stub with mirofish_client.py integration and
           return ValidationResult populated from simulation output.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas import PRDDocument, ValidationResult

router = APIRouter(prefix="/validation", tags=["validation"])


class ValidationRequest(BaseModel):
    """Request to trigger PRD validation."""

    project_id: str
    prd: PRDDocument


class ValidationResponse(BaseModel):
    """Validation response — stub until T05."""

    project_id: str
    status: str
    result: ValidationResult | None = None


@router.post("/run", response_model=ValidationResponse)
async def run_validation(body: ValidationRequest) -> ValidationResponse:
    """
    Trigger MiroFish simulation validation for a PRD document.
    TODO(T05): Implement validation packaging and MiroFish client call.
    """
    return ValidationResponse(
        project_id=body.project_id,
        status="pending",
        result=None,
    )
