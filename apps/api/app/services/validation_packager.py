"""
services/validation_packager.py — PRD → MiroFish simulation spec packager.

Public API
----------
    package_for_simulation(prd_doc: PRDDocument) -> SimulationSpec

Design contract
---------------
- Pure function: PRDDocument in → SimulationSpec out.
- The only permitted side-effect is UUID4 generation (spec_id) and
  datetime.now() for created_at — both are deterministic in test context
  when mocked.
- Internally calls render_prd_markdown() (T04) to produce prd_markdown.
- Does NOT make any HTTP calls — actual MiroFish invocation is T10.
- focus_areas auto-extraction:
    1. risks[].title  (ordered, preserves PRD order)
    2. open_questions[].text  (ordered, preserves PRD order)
  Rationale: risks and open questions are the highest-signal inputs for
  the simulation engine; surfacing them explicitly avoids forcing the
  simulator to re-parse the full PRD text.

Scope guard
-----------
- HTTP calls: T10
- ValidationResult generation / mock engine: T06
- Chat orchestration: T03
- Markdown renderer logic: T04 (call it, don't change it)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas import PRDDocument
from app.schemas.simulation import SimulationSpec, ValidationConfig
from app.services.markdown_renderer import render_prd_markdown


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_prd_summary(prd_doc: PRDDocument) -> dict[str, Any]:
    """
    Build the compact prd_summary dict.

    Fields:
        name        – product name (str)
        one_liner   – product one-liner description (str)
        category    – product category (str)
        stage       – product stage enum value (str)
        project_id  – metadata project identifier (str)
    """
    product = prd_doc.product
    metadata = prd_doc.metadata
    return {
        "name": product.name,
        "one_liner": product.one_liner,
        "category": product.category,
        "stage": product.stage.value if hasattr(product.stage, "value") else str(product.stage),
        "project_id": metadata.project_id,
    }


def _extract_focus_areas(prd_doc: PRDDocument) -> list[str]:
    """
    Auto-generate focus_areas by concatenating:
      1. risks[].title       — areas the simulation should stress-test
      2. open_questions[].text — questions the simulation must answer

    Order is preserved from the PRD.
    """
    focus: list[str] = []

    for risk in prd_doc.risks:
        title = risk.title
        if title and title.strip():
            focus.append(title.strip())

    for question in prd_doc.open_questions:
        text = question.text
        if text and text.strip():
            focus.append(text.strip())

    return focus


def _build_validation_config(prd_doc: PRDDocument) -> ValidationConfig:
    """
    Build ValidationConfig from PRDDocument.validation + auto-extracted focus_areas.
    """
    val = prd_doc.validation

    # Stakeholders: serialise to plain dict (enum values → str via model_dump)
    stakeholder_dicts: list[dict[str, Any]] = [
        s.model_dump() for s in val.stakeholder_personas
    ]

    # validation_templates: list[ValidationTemplate] | None → list[str]
    templates: list[str] = []
    if val.validation_templates:
        templates = [
            t.value if hasattr(t, "value") else str(t)
            for t in val.validation_templates
        ]

    # must_answer_questions: list[str] | None → list[str]
    must_answer: list[str] = val.must_answer_questions or []

    # focus_areas: auto-extracted from risks + open_questions
    focus_areas = _extract_focus_areas(prd_doc)

    return ValidationConfig(
        goals=val.goals,
        stakeholder_personas=stakeholder_dicts,
        simulation_requirement=val.simulation_requirement,
        validation_templates=templates,
        must_answer_questions=must_answer,
        focus_areas=focus_areas,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def package_for_simulation(prd_doc: PRDDocument) -> SimulationSpec:
    """
    Convert a validated PRDDocument into a MiroFish SimulationSpec.

    Parameters
    ----------
    prd_doc : PRDDocument
        A fully-constructed Pydantic PRDDocument instance.
        Must have passed T02 JSON Schema validation before reaching this point.

    Returns
    -------
    SimulationSpec
        A self-contained simulation input payload ready for MiroFish.
        The caller may inspect it, log it, or pass it to
        mirofish_client.run_validation(spec) [T10].

    Notes
    -----
    - spec_id is a fresh UUID4 — unique per call.
    - prd_markdown is rendered by calling render_prd_markdown() with
      the model_dump() output (enum values already normalised by _safe()).
    - prd_structured stores the raw model_dump() so T02 can re-validate
      at any downstream step.
    """
    # 1. Serialise PRD to plain dict (enums → .value via mode="json")
    prd_dict: dict[str, Any] = prd_doc.model_dump(mode="json")

    # 2. Render Markdown (T04)
    prd_markdown: str = render_prd_markdown(prd_dict)

    # 3. Build compact summary
    prd_summary = _extract_prd_summary(prd_doc)

    # 4. Build ValidationConfig
    validation_config = _build_validation_config(prd_doc)

    # 5. Assemble SimulationSpec
    return SimulationSpec(
        spec_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        prd_summary=prd_summary,
        prd_structured=prd_dict,
        prd_markdown=prd_markdown,
        validation_config=validation_config,
    )
