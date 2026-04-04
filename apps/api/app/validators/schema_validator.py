"""
validators/schema_validator.py — JSON Schema–level PRD validation.

Purpose
-------
Validates a raw dict (parsed JSON payload) against PRD_SCHEMA.json using
jsonschema Draft7Validator.  This is a *boundary-level* check that runs
before — and independently of — Pydantic model_validate().

Why two layers?
    Pydantic (T01):  Pythonic runtime typing; optional fields get defaults;
                     dict → model object conversion.
    JSON Schema (T02): Contract enforcement at the data boundary; catches
                       additionalProperties violations, required-array gaps
                       in ValidationResult, and enum mismatches before any
                       Python model is constructed.

Key design decisions
--------------------
- PRD_SCHEMA.json is loaded once at module import time and cached in the
  module-level ``_VALIDATOR`` singleton.  Subsequent calls to
  ``get_validator()`` / ``validate_prd()`` pay no I/O cost.
- Errors are collected via ``iter_errors()`` so ALL violations are reported
  in one pass (fail-fast is NOT used).
- ``ValidationReport`` is a plain dataclass — no Pydantic dependency — so
  it can be used anywhere without circular imports.
- SCHEMA DRIFT resolution (T01 note):  ValidationResult list fields
  (top_risks, missing_requirements, etc.) are "required" in the JSON Schema,
  meaning the payload MUST include them even as empty arrays.  This validator
  enforces that constraint; Pydantic's default_factory is only for in-code
  construction convenience.

Scope guard
-----------
- NO MiroFish integration (T10)
- NO chat orchestration (T03)
- NO markdown rendering (T04)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError, ValidationError

# ---------------------------------------------------------------------------
# Schema path resolution
# ---------------------------------------------------------------------------
# Walk up from this file to the repo root, then locate PRD_SCHEMA.json.
# Layout:  apps/api/app/validators/schema_validator.py
#          apps/api/app/
#          apps/api/
#          apps/
#          <repo_root>/PRD_SCHEMA.json
_REPO_ROOT: Path = Path(__file__).resolve().parents[4]
PRD_SCHEMA_PATH: Path = _REPO_ROOT / "PRD_SCHEMA.json"


# ---------------------------------------------------------------------------
# ValidationReport — structured result returned by validate_prd()
# ---------------------------------------------------------------------------
@dataclass
class SchemaError_:
    """A single JSON Schema validation error."""

    message: str
    """Human-readable error message from jsonschema."""
    path: str
    """JSON path to the offending field (dot-notation, e.g. 'metadata.status')."""
    schema_path: str
    """Path within the JSON Schema that was violated."""
    validator: str
    """The JSON Schema keyword that failed (e.g. 'required', 'enum', 'additionalProperties')."""


@dataclass
class ValidationReport:
    """
    Structured result of a JSON Schema validation run.

    Attributes
    ----------
    valid:   True iff the payload satisfies every constraint in PRD_SCHEMA.json.
    errors:  List of all constraint violations (empty when valid=True).
    schema_version: The schema_version field extracted from the payload
                    (or None if not present / not a string).
    """

    valid: bool
    errors: list[SchemaError_] = field(default_factory=list)
    schema_version: str | None = None

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def first_error_message(self) -> str | None:
        """Convenience accessor for the first error message (or None)."""
        return self.errors[0].message if self.errors else None


# ---------------------------------------------------------------------------
# Validator singleton
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_validator() -> Draft7Validator:
    """
    Load PRD_SCHEMA.json and return a cached Draft7Validator instance.

    The validator is constructed once and reused for every call to
    validate_prd().  Raises RuntimeError if the schema file is missing
    or the schema itself is malformed.

    Raises
    ------
    FileNotFoundError  – PRD_SCHEMA.json not found at expected path.
    SchemaError        – PRD_SCHEMA.json is not a valid JSON Schema.
    """
    if not PRD_SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"PRD_SCHEMA.json not found at {PRD_SCHEMA_PATH}. "
            "Ensure the repo root contains PRD_SCHEMA.json."
        )

    schema: dict[str, Any] = json.loads(PRD_SCHEMA_PATH.read_text(encoding="utf-8"))

    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaError(
            f"PRD_SCHEMA.json is not a valid JSON Schema: {exc.message}"
        ) from exc

    return Draft7Validator(schema)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def validate_prd(payload: dict[str, Any]) -> ValidationReport:
    """
    Validate a raw PRD payload dict against PRD_SCHEMA.json.

    This function is the primary public interface for T02 validation.
    It is intentionally decoupled from Pydantic so it can be called:
        - before model construction (raw boundary check)
        - on payloads that arrive as plain JSON (e.g. from HTTP body bytes)
        - in tests without FastAPI context

    Parameters
    ----------
    payload : dict
        Parsed JSON object to validate.  Must be a dict; passing a non-dict
        (e.g. list or string) will produce a type-error in the report.

    Returns
    -------
    ValidationReport
        ``valid=True`` with empty ``errors`` if the payload is conformant.
        ``valid=False`` with one or more ``SchemaError_`` entries otherwise.

    Notes
    -----
    - ALL errors are collected (not fail-fast).
    - SCHEMA DRIFT resolution: ValidationResult's list fields are "required"
      in the JSON Schema.  A payload that omits them (e.g. provides only
      ``summary``) will be reported as invalid here, even though Pydantic
      would accept it via default_factory.
    """
    validator = get_validator()

    raw_errors: list[ValidationError] = sorted(
        validator.iter_errors(payload),
        key=lambda e: list(e.absolute_path),
    )

    if not raw_errors:
        schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
        return ValidationReport(
            valid=True,
            errors=[],
            schema_version=schema_version if isinstance(schema_version, str) else None,
        )

    structured_errors: list[SchemaError_] = [
        SchemaError_(
            message=err.message,
            path=_path_to_str(err.absolute_path),
            schema_path=_path_to_str(err.absolute_schema_path),
            validator=err.validator,
        )
        for err in raw_errors
    ]

    schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
    return ValidationReport(
        valid=False,
        errors=structured_errors,
        schema_version=schema_version if isinstance(schema_version, str) else None,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _path_to_str(path: Any) -> str:
    """Convert a jsonschema deque-path to a readable dot-notation string."""
    parts = list(path)
    if not parts:
        return "(root)"
    return ".".join(str(p) for p in parts)
