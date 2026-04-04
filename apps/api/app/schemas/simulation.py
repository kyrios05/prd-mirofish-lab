"""
schemas/simulation.py — MiroFish simulation payload models.

These models define the structured input sent to the MiroFish simulation
engine.  They are produced by validation_packager.py (T05) and consumed
by mirofish_client.py (T10).

Dependency chain (no cycles):
    enums → common → prd → simulation → validation_packager → mirofish_client

Models
------
ValidationConfig
    All parameters that control what the MiroFish simulation will evaluate.
    Extracted from PRDDocument.validation + auto-generated focus_areas.

SimulationSpec
    The complete, self-contained input payload for one MiroFish run.
    Contains both the full PRD (structured + Markdown) and the validation
    configuration so the simulation engine needs nothing else.

Design notes
------------
- ConfigDict(extra="forbid") on all models — consistent with the rest of
  the schemas package.
- All fields are JSON-serialisable (str, list, dict) so SimulationSpec can
  be sent over HTTP without further conversion.
- spec_id is a UUID4 string assigned at packaging time.
- prd_structured stores the raw PRDDocument.model_dump() output so that
  T02's validate_prd() can be called on it at any downstream step.
- Scope guard: no HTTP calls, no I/O — pure data containers.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# ValidationConfig
# ---------------------------------------------------------------------------

class ValidationConfig(BaseModel):
    """
    Validation-run configuration extracted from PRDDocument.validation.

    Maps to PRD_SCHEMA.json #/properties/validation, with the addition of
    focus_areas (auto-generated from risks + open_questions).

    Scope: T05 packages this.  T10 sends it to MiroFish.  T06 interprets it.
    """

    model_config = ConfigDict(extra="forbid")

    goals: list[str] = Field(
        ...,
        min_length=1,
        description="Validation goals copied verbatim from PRDDocument.validation.goals.",
    )
    stakeholder_personas: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description=(
            "Serialised Stakeholder objects (model_dump() output). "
            "Each dict contains: name, role, review_angle, likely_objections."
        ),
    )
    simulation_requirement: str = Field(
        ...,
        min_length=1,
        description="Minimum simulation fidelity requirement for this PRD.",
    )
    validation_templates: list[str] = Field(
        default_factory=list,
        description=(
            "Predefined MiroFish validation template IDs to apply. "
            "Empty list when PRD.validation.validation_templates is None."
        ),
    )
    must_answer_questions: list[str] = Field(
        default_factory=list,
        description=(
            "Questions the simulation MUST answer before approval. "
            "Empty list when PRD.validation.must_answer_questions is None."
        ),
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description=(
            "Auto-generated list of areas requiring special attention during simulation. "
            "Derived by concatenating risks[].title followed by open_questions[].text. "
            "The simulation engine uses these as priority signals."
        ),
    )


# ---------------------------------------------------------------------------
# SimulationSpec
# ---------------------------------------------------------------------------

class SimulationSpec(BaseModel):
    """
    Complete, self-contained MiroFish simulation input payload.

    Produced by: validation_packager.package_for_simulation(prd_doc)
    Consumed by: mirofish_client.run_validation(spec)  [T10]

    The spec is designed to be fully self-describing — it carries both the
    raw structured PRD (for T02 re-validation) and the Markdown rendering
    (for human-readable context in the simulation UI) alongside the
    validation configuration.

    JSON-serialisable: all fields are str / list / dict — safe for HTTP
    transport without additional conversion.
    """

    model_config = ConfigDict(extra="forbid")

    spec_id: str = Field(
        ...,
        description="UUID4 identifier for this simulation spec instance.",
    )
    created_at: str = Field(
        ...,
        description="ISO-8601 timestamp of when this spec was packaged.",
    )
    prd_summary: dict[str, Any] = Field(
        ...,
        description=(
            "High-level PRD identity extracted for quick reference. "
            "Keys: name, one_liner, category, stage, project_id."
        ),
    )
    prd_structured: dict[str, Any] = Field(
        ...,
        description=(
            "Full PRDDocument.model_dump() output. "
            "T02's validate_prd() can be called on this dict at any time."
        ),
    )
    prd_markdown: str = Field(
        ...,
        min_length=1,
        description="T04 Markdown rendering of the PRD (render_prd_markdown output).",
    )
    validation_config: ValidationConfig = Field(
        ...,
        description="Validation run parameters including auto-generated focus_areas.",
    )

    # ------------------------------------------------------------------
    # Convenience helpers (do NOT add side-effects here)
    # ------------------------------------------------------------------

    def summary_dict(self) -> dict[str, Any]:
        """Return a compact dict for logging / debug — omits large text fields."""
        return {
            "spec_id": self.spec_id,
            "created_at": self.created_at,
            "prd_summary": self.prd_summary,
            "goals_count": len(self.validation_config.goals),
            "stakeholders_count": len(self.validation_config.stakeholder_personas),
            "focus_areas_count": len(self.validation_config.focus_areas),
            "prd_markdown_chars": len(self.prd_markdown),
        }
