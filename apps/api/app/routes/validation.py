"""
routes/validation.py — PRD validation + simulation spec packaging endpoints.

Pipeline
--------
  POST /validation/run
    Step 1 (T02): JSON Schema validation via validate_prd()
    Step 2 (T02): Pydantic model construction — PRDDocument.model_validate()
    Step 3 (T05): Simulation spec packaging via package_for_simulation()
    Step 4 (T10): MiroFishClient.run_validation(spec) — mock by default;
                       switches to real MiroFish in MIROFISH_MODE=live.

  POST /validation/schema-check  (T02, unchanged)
    JSON Schema validation only — no Pydantic, no packaging

  POST /validation/package  (T05, unchanged)
    Schema validation + Pydantic construction + packaging only.
    Lightweight endpoint for CI/CD spec inspection / debugging.
    Does NOT trigger mock validation. status='packaged', result=None.

Scope guard
-----------
- MiroFish HTTP invocation: T10
- Schema / SimulationSpec model changes: T01/T05 frozen
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.schemas import PRDDocument, SimulationSpec, ValidationResult
from app.services.mirofish_client import make_mirofish_client
from app.services.validation_packager import package_for_simulation
from app.validators.schema_validator import ValidationReport, validate_prd

router = APIRouter(prefix="/validation", tags=["validation"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ValidationRequest(BaseModel):
    """
    Request to trigger PRD validation / packaging.

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
    """
    Validation + packaging response.

    schema_valid:      True iff the payload passed PRD_SCHEMA.json validation.
    schema_errors:     List of JSON Schema violations (empty when schema_valid=True).
    status:            One of:
                         'schema_invalid'  — JSON Schema check failed
                         'packaged'        — spec built, validation NOT run (/package endpoint)
                         'completed'       — spec built + validation run (/run endpoint)
                         'schema_valid'    — schema-check only endpoint
    simulation_spec:   SimulationSpec.model_dump() when status in ('packaged','completed').
    result:            ValidationResult on /run; None on /package.
    validation_mode:   'mock' or 'live' — which engine produced the result.
    job:               MiroFishJob.to_dict() when mode='live'; None in mock mode.
    """

    project_id: str
    schema_valid: bool
    schema_errors: list[SchemaErrorItem] = []
    status: str
    simulation_spec: dict[str, Any] | None = None
    result: ValidationResult | None = None
    # T10 additions
    validation_mode: str = "mock"          # "mock" | "live"
    job: dict[str, Any] | None = None      # MiroFishJob.to_dict() in live mode


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _schema_error_items(report: ValidationReport) -> list[SchemaErrorItem]:
    return [
        SchemaErrorItem(
            message=err.message,
            path=err.path,
            schema_path=err.schema_path,
            validator=err.validator,
        )
        for err in report.errors
    ]


def _validate_and_build_prd(
    project_id: str,
    prd_dict: dict,
) -> tuple[ValidationReport, PRDDocument | None, ValidationResponse | None]:
    """
    Run Step 1 (JSON Schema) + Step 2 (Pydantic).

    Returns (report, prd_doc, early_response).
    - If schema fails: early_response is set (caller should return it).
    - If Pydantic fails: raises HTTP 500.
    - On success: prd_doc is the constructed PRDDocument.
    """
    # Step 1: JSON Schema
    report: ValidationReport = validate_prd(prd_dict)
    if not report.valid:
        return report, None, ValidationResponse(
            project_id=project_id,
            schema_valid=False,
            schema_errors=_schema_error_items(report),
            status="schema_invalid",
            simulation_spec=None,
            result=None,
        )

    # Step 2: Pydantic construction
    try:
        prd_doc: PRDDocument = PRDDocument.model_validate(prd_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Schema passed JSON Schema validation but failed Pydantic construction. "
                "This indicates a schema drift — please update PRD_SCHEMA.json or the "
                f"Pydantic models to stay in sync. Details: {exc}"
            ),
        ) from exc

    return report, prd_doc, None


# ---------------------------------------------------------------------------
# POST /validation/run  — full pipeline (T02 + T05 + T06, T10 stub)
# ---------------------------------------------------------------------------

@router.post("/run", response_model=ValidationResponse)
async def run_validation(body: ValidationRequest) -> ValidationResponse:
    """
    Validate a PRD document, package it as a SimulationSpec, and run validation.

    Step 1 (T02): JSON Schema validation.
    Step 2 (T02): Pydantic model construction.
    Step 3 (T05): SimulationSpec packaging via package_for_simulation().
    Step 4 (T10): MiroFishClient.run_validation(spec).
                  MIROFISH_MODE=mock (default) → mock engine (T06 behaviour).
                  MIROFISH_MODE=live → real MiroFish adapter with fallback.

    Returns 422 if the request payload is malformed.
    Returns 200 with schema_valid=False if PRD_SCHEMA.json constraints fail.
    Returns 200 with status='completed', simulation_spec, result, and
            validation_mode / job metadata on success.
    """
    report, prd_doc, early = _validate_and_build_prd(body.project_id, body.prd)
    if early is not None:
        return early

    # Step 3 (T05): Package into SimulationSpec
    spec: SimulationSpec = package_for_simulation(prd_doc)

    # Step 4 (T10): Run via MiroFishClient (mock or live depending on config)
    client = make_mirofish_client()
    result: ValidationResult | None = await client.run_validation(spec)

    # Collect mode/job metadata for the response
    validation_mode: str = client.mode if client.mode in ("mock", "live") else "mock"
    job_dict: dict[str, Any] | None = (
        client.last_job.to_dict() if client.last_job is not None else None
    )

    return ValidationResponse(
        project_id=body.project_id,
        schema_valid=True,
        schema_errors=[],
        status="completed",
        simulation_spec=spec.model_dump(),
        result=result,
        validation_mode=validation_mode,
        job=job_dict,
    )


# ---------------------------------------------------------------------------
# POST /validation/schema-check  — schema only (T02, unchanged)
# ---------------------------------------------------------------------------

@router.post("/schema-check", response_model=ValidationResponse)
async def schema_check(body: ValidationRequest) -> ValidationResponse:
    """
    Run JSON Schema validation only — no Pydantic construction, no packaging.

    Useful for:
    - Quick client-side validation before submitting a full run.
    - CI/CD payload linting.
    - Debugging schema drift between PRD_SCHEMA.json and client payloads.
    """
    report: ValidationReport = validate_prd(body.prd)
    return ValidationResponse(
        project_id=body.project_id,
        schema_valid=report.valid,
        schema_errors=_schema_error_items(report),
        status="schema_valid" if report.valid else "schema_invalid",
        simulation_spec=None,
        result=None,
    )


# ---------------------------------------------------------------------------
# POST /validation/package  — packaging only (T05, new)
# ---------------------------------------------------------------------------

@router.post("/package", response_model=ValidationResponse)
async def package_only(body: ValidationRequest) -> ValidationResponse:
    """
    Run schema validation + Pydantic construction + SimulationSpec packaging.

    Does NOT trigger a MiroFish simulation run.  Intended for:
    - CI/CD spec shape inspection before integration testing.
    - Debugging packaging logic independently of MiroFish availability.
    - Generating simulation_spec for manual review.

    Returns 200 with status='packaged' and simulation_spec on success.
    Returns 200 with schema_valid=False on schema violation.
    """
    report, prd_doc, early = _validate_and_build_prd(body.project_id, body.prd)
    if early is not None:
        return early

    spec: SimulationSpec = package_for_simulation(prd_doc)

    return ValidationResponse(
        project_id=body.project_id,
        schema_valid=True,
        schema_errors=[],
        status="packaged",
        simulation_spec=spec.model_dump(),
        result=None,
    )
