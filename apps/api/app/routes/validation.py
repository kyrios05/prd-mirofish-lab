"""
routes/validation.py — PRD validation endpoint.

T02 scope: JSON Schema validation is wired in.
           validate_prd() runs before Pydantic construction so boundary-level
           errors (additionalProperties, required list fields, enum mismatches)
           are caught and returned as structured errors.

NOTE(T05): Replace the stub body of run_validation() with mirofish_client.py
           integration and populate ValidationResult from simulation output.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.schemas import PRDDocument, ValidationResult
from app.validators.schema_validator import ValidationReport, validate_prd

router = APIRouter(prefix="/validation", tags=["validation"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ValidationRequest(BaseModel):
    """Request to trigger PRD validation.

    The ``prd`` field accepts a raw dict so that JSON Schema validation
    can run on the original payload before Pydantic model construction.
    After schema validation passes, the dict is coerced into a PRDDocument.
    """

    project_id: str
    prd: dict  # raw dict — schema-validated before Pydantic construction


class SchemaErrorItem(BaseModel):
    """A single JSON Schema constraint violation."""

    message: str
    path: str
    schema_path: str
    validator: str


class ValidationResponse(BaseModel):
    """Validation response.

    schema_valid:   True iff the payload passed PRD_SCHEMA.json validation.
    schema_errors:  List of JSON Schema violations (empty when schema_valid=True).
    status:         'schema_invalid' | 'pending' | 'completed'
    result:         MiroFish simulation result — populated in T05.
    """

    project_id: str
    schema_valid: bool
    schema_errors: list[SchemaErrorItem] = []
    status: str
    result: ValidationResult | None = None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post("/run", response_model=ValidationResponse)
async def run_validation(body: ValidationRequest) -> ValidationResponse:
    """
    Validate a PRD document against PRD_SCHEMA.json and trigger simulation.

    Step 1 (T02): JSON Schema validation via validate_prd().
    Step 2 (T05, TODO): Package PRD and call MiroFish client.

    Returns 422 if the payload itself is malformed JSON structure.
    Returns 200 with schema_valid=False if schema constraints are violated
    (errors are surfaced in schema_errors for caller inspection).
    """
    # ── Step 1: JSON Schema validation (T02) ────────────────────────────────
    report: ValidationReport = validate_prd(body.prd)

    if not report.valid:
        return ValidationResponse(
            project_id=body.project_id,
            schema_valid=False,
            schema_errors=[
                SchemaErrorItem(
                    message=err.message,
                    path=err.path,
                    schema_path=err.schema_path,
                    validator=err.validator,
                )
                for err in report.errors
            ],
            status="schema_invalid",
            result=None,
        )

    # ── Step 2: Pydantic construction (safe — schema already validated) ──────
    try:
        prd_doc: PRDDocument = PRDDocument.model_validate(body.prd)
    except Exception as exc:
        # Pydantic errors after a passing schema check indicate a schema drift.
        # Surface as 500 so it is visible and actionable.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Schema passed JSON Schema validation but failed Pydantic construction. "
                f"This indicates a schema drift — please update PRD_SCHEMA.json or the "
                f"Pydantic models to stay in sync. Details: {exc}"
            ),
        ) from exc

    # ── Step 3: MiroFish simulation (T05 — stub) ─────────────────────────────
    # TODO(T05): Package prd_doc into MiroFish simulation spec and call
    #            mirofish_client.run_validation(prd_doc).
    _ = prd_doc  # suppress unused warning until T05

    return ValidationResponse(
        project_id=body.project_id,
        schema_valid=True,
        schema_errors=[],
        status="pending",
        result=None,
    )


# ---------------------------------------------------------------------------
# Schema-only validation endpoint (lightweight, no Pydantic construction)
# ---------------------------------------------------------------------------
@router.post("/schema-check", response_model=ValidationResponse)
async def schema_check(body: ValidationRequest) -> ValidationResponse:
    """
    Run JSON Schema validation only — no Pydantic construction, no MiroFish.

    Useful for:
    - Quick client-side validation before submitting a full run
    - CI/CD payload linting
    - Debugging schema drift between PRD_SCHEMA.json and client payloads
    """
    report: ValidationReport = validate_prd(body.prd)
    return ValidationResponse(
        project_id=body.project_id,
        schema_valid=report.valid,
        schema_errors=[
            SchemaErrorItem(
                message=err.message,
                path=err.path,
                schema_path=err.schema_path,
                validator=err.validator,
            )
            for err in report.errors
        ],
        status="schema_valid" if report.valid else "schema_invalid",
        result=None,
    )
