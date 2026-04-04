"""
common.py — Reusable sub-models ($defs) for the PRD domain.

Source of truth: PRD_SCHEMA.json $defs section (9 sub-models)
Dependency: enums (one-way; never import from prd.py)

Sub-models defined here:
    Persona, Stakeholder, Feature, Requirement, Integration,
    Metric, TaggedItem, Risk, ValidationResult
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    FeaturePriority,
    IntegrationType,
    Priority,
    Severity,
)


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------
class Persona(BaseModel):
    """A user archetype with goals and pain points.
    Maps to PRD_SCHEMA.json $defs/Persona.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Display name of the persona")
    role: str = Field(..., min_length=1, description="Job title or role label")
    goals: list[str] = Field(
        ..., min_length=1, description="What this persona is trying to achieve"
    )
    pain_points: list[str] = Field(
        ..., min_length=1, description="Frustrations with the current state"
    )
    company_type: Optional[str] = Field(
        None, description="Type of organization the persona works in"
    )
    context: Optional[str] = Field(
        None, description="Additional context about the persona's situation"
    )


# ---------------------------------------------------------------------------
# Stakeholder
# ---------------------------------------------------------------------------
class Stakeholder(BaseModel):
    """A validation stakeholder who reviews the PRD from a specific angle.
    Maps to PRD_SCHEMA.json $defs/Stakeholder.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Stakeholder name or role label")
    role: str = Field(..., min_length=1, description="Organizational role")
    review_angle: str = Field(
        ..., min_length=1, description="What aspect of the PRD this stakeholder evaluates"
    )
    likely_objections: Optional[list[str]] = Field(
        None, description="Anticipated objections this stakeholder might raise"
    )


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------
class Feature(BaseModel):
    """A product feature with MoSCoW priority.
    Maps to PRD_SCHEMA.json $defs/Feature.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Short feature name")
    description: str = Field(..., min_length=1, description="What the feature does")
    priority: FeaturePriority = Field(
        ..., description="MoSCoW priority classification"
    )
    rationale: Optional[str] = Field(
        None, description="Why this feature is included or excluded"
    )


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------
class Requirement(BaseModel):
    """A single functional or non-functional requirement.
    Maps to PRD_SCHEMA.json $defs/Requirement.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Unique requirement identifier, e.g. 'FR-01'")
    statement: str = Field(..., min_length=1, description="The requirement statement")
    priority: Optional[Priority] = Field(
        None, description="Implementation priority"
    )
    notes: Optional[str] = Field(None, description="Additional clarification notes")


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------
class Integration(BaseModel):
    """An external system or service integration.
    Maps to PRD_SCHEMA.json $defs/Integration.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Name of the integration (e.g. 'Stripe')")
    type: IntegrationType = Field(..., description="Category of integration")
    purpose: Optional[str] = Field(
        None, description="Why this integration is needed"
    )


# ---------------------------------------------------------------------------
# Metric
# ---------------------------------------------------------------------------
class Metric(BaseModel):
    """A measurable success or guardrail metric.
    Maps to PRD_SCHEMA.json $defs/Metric.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Metric name")
    target: str = Field(..., min_length=1, description="Target value or threshold")
    timeframe: Optional[str] = Field(
        None, description="Measurement timeframe (e.g. '3 months post-launch')"
    )
    notes: Optional[str] = Field(None, description="Additional measurement notes")


# ---------------------------------------------------------------------------
# TaggedItem  (shared by assumptions and open_questions arrays)
# ---------------------------------------------------------------------------
class TaggedItem(BaseModel):
    """A text item with an optional tag and severity label.
    Maps to PRD_SCHEMA.json $defs/TaggedItem.
    Used by: assumptions[], open_questions[]
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, description="The assumption or open question text")
    tag: Optional[str] = Field(
        None, description="Category tag (e.g. 'technical', 'business')"
    )
    severity: Optional[Severity] = Field(
        None, description="How critical this item is if wrong"
    )


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------
class Risk(BaseModel):
    """A project or product risk.
    Maps to PRD_SCHEMA.json $defs/Risk.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, description="Short risk title")
    description: str = Field(..., min_length=1, description="Detailed risk description")
    severity: Severity = Field(..., description="How severe the risk is")
    mitigation: Optional[str] = Field(
        None, description="How we plan to mitigate this risk"
    )
    owner: Optional[str] = Field(None, description="Who is responsible for this risk")


# ---------------------------------------------------------------------------
# ValidationResult  (stored inside artifacts, populated by MiroFish)
# ---------------------------------------------------------------------------
class ValidationResult(BaseModel):
    """The output of a MiroFish simulation validation run.
    Maps to PRD_SCHEMA.json $defs/ValidationResult.
    NOTE: This model is read-only from the PRD author's perspective.
          Populated by the validation packager (T05 scope).
    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1, description="High-level validation summary")
    top_risks: list[str] = Field(
        default_factory=list, description="Most critical risks identified"
    )
    missing_requirements: list[str] = Field(
        default_factory=list, description="Requirements gaps found during validation"
    )
    stakeholder_objections: list[str] = Field(
        default_factory=list, description="Objections raised by simulated stakeholders"
    )
    scope_adjustments: list[str] = Field(
        default_factory=list, description="Recommended scope changes"
    )
    recommended_questions: list[str] = Field(
        default_factory=list, description="Follow-up questions to clarify"
    )
    rewrite_suggestions: list[str] = Field(
        default_factory=list, description="Specific rewrites suggested for PRD sections"
    )
