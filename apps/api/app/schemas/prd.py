"""
prd.py — Top-level PRDDocument model + all 14 section models.

Source of truth: PRD_SCHEMA.json (top-level required + optional sections)
Dependency: enums, common (one-way; do NOT import from routes/services)

Section models:
    Source, Metadata, Product, Users, Problem, Solution, Scope,
    Requirements, SuccessMetrics, Delivery, ValidationSection, Artifacts

Top-level model:
    PRDDocument
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import (
    Feature,
    Integration,
    Metric,
    Persona,
    Requirement,
    Risk,
    Stakeholder,
    TaggedItem,
    ValidationResult,
)
from .enums import (
    Language,
    Platform,
    PrdStatus,
    Priority,
    ProductStage,
    SourceMode,
    TimelineConfidence,
    ValidationTemplate,
)


# ---------------------------------------------------------------------------
# metadata.source (nested object)
# ---------------------------------------------------------------------------
class Source(BaseModel):
    """How the PRD was created — mode, session context.
    Maps to PRD_SCHEMA.json $defs/Source (nested inside Metadata).
    """

    model_config = ConfigDict(extra="forbid")

    mode: SourceMode = Field(..., description="Creation mode: chat | form | import")
    chat_turn_count: Optional[int] = Field(
        None, ge=0, description="Number of chat turns used to build the PRD"
    )
    session_id: Optional[str] = Field(
        None, min_length=1, description="Chat session identifier"
    )
    notes: Optional[str] = Field(None, description="Free-form creation notes")


# ---------------------------------------------------------------------------
# Metadata section
# ---------------------------------------------------------------------------
class Metadata(BaseModel):
    """Document identity and lifecycle metadata.
    Maps to PRD_SCHEMA.json #/properties/metadata.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ..., min_length=1, description="Unique project identifier (slug or UUID)"
    )
    created_at: str = Field(
        ..., description="ISO-8601 datetime when the PRD was first created"
    )
    updated_at: str = Field(
        ..., description="ISO-8601 datetime of the last update"
    )
    language: Language = Field(..., description="Document language")
    status: PrdStatus = Field(..., description="Current lifecycle status")
    source: Source = Field(..., description="How this PRD was created")
    owner: Optional[str] = Field(None, description="PRD owner / author name")
    version: Optional[str] = Field(
        None, description="Semantic version of this PRD draft"
    )


# ---------------------------------------------------------------------------
# Product section
# ---------------------------------------------------------------------------
class Product(BaseModel):
    """Core product identity.
    Maps to PRD_SCHEMA.json #/properties/product.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Product name")
    one_liner: str = Field(
        ..., min_length=1, description="One-sentence product description"
    )
    category: str = Field(
        ..., min_length=1, description="Product category (e.g. 'SaaS', 'Developer Tool')"
    )
    platforms: list[Platform] = Field(
        ..., min_length=1, description="Target delivery platforms"
    )
    stage: ProductStage = Field(..., description="Current product maturity stage")
    industry_context: Optional[list[str]] = Field(
        None, description="Industry or vertical context tags (e.g. ['B2B SaaS', 'Fintech'])"
    )
    domain_context: Optional[str] = Field(
        None, description="Technical or functional domain context (free-text)"
    )


# ---------------------------------------------------------------------------
# Users section
# ---------------------------------------------------------------------------
class Users(BaseModel):
    """User persona definitions.
    Maps to PRD_SCHEMA.json #/properties/users.
    """

    model_config = ConfigDict(extra="forbid")

    primary_personas: list[Persona] = Field(
        ..., min_length=1, description="Primary target user personas"
    )
    secondary_personas: Optional[list[Persona]] = Field(
        None, description="Secondary personas that may use the product"
    )
    non_targets: Optional[list[str]] = Field(
        None, description="User groups explicitly excluded from scope"
    )


# ---------------------------------------------------------------------------
# Problem section
# ---------------------------------------------------------------------------
class Problem(BaseModel):
    """Problem definition and context.
    Maps to PRD_SCHEMA.json #/properties/problem.
    """

    model_config = ConfigDict(extra="forbid")

    core_problem: str = Field(
        ..., min_length=1, description="The primary problem this product solves"
    )
    pain_points: list[str] = Field(
        ..., min_length=1, description="Specific pain points experienced by users"
    )
    current_alternatives: list[str] = Field(
        ...,
        min_length=1,
        description="How users solve this problem today (status quo)",
    )
    why_now: Optional[str] = Field(
        None, description="Why this problem is worth solving now"
    )
    jobs_to_be_done: Optional[list[str]] = Field(
        None, description="JTBD framework statements"
    )


# ---------------------------------------------------------------------------
# Solution section
# ---------------------------------------------------------------------------
class Solution(BaseModel):
    """Proposed solution and key features.
    Maps to PRD_SCHEMA.json #/properties/solution.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1, description="High-level solution summary")
    value_proposition: str = Field(
        ..., min_length=1, description="Core value proposition for target users"
    )
    key_features: list[Feature] = Field(
        ..., min_length=1, description="Key product features with MoSCoW priority"
    )
    user_journey: Optional[list[str]] = Field(
        None, description="Ordered steps of the user journey through the solution"
    )


# ---------------------------------------------------------------------------
# Scope section
# ---------------------------------------------------------------------------
class Scope(BaseModel):
    """MVP scope definition — what's in, what's out.
    Maps to PRD_SCHEMA.json #/properties/scope.
    """

    model_config = ConfigDict(extra="forbid")

    mvp_in_scope: list[str] = Field(
        ..., min_length=1, description="Features / capabilities included in MVP"
    )
    out_of_scope: list[str] = Field(
        ..., min_length=1, description="Explicitly excluded from this release"
    )
    future_expansion: Optional[list[str]] = Field(
        None, description="Items planned for post-MVP phases"
    )
    launch_constraints: Optional[list[str]] = Field(
        None, description="Hard constraints on launch (regulatory, technical, budget)"
    )


# ---------------------------------------------------------------------------
# Requirements section
# ---------------------------------------------------------------------------
class Requirements(BaseModel):
    """Functional and non-functional requirements.
    Maps to PRD_SCHEMA.json #/properties/requirements.
    """

    model_config = ConfigDict(extra="forbid")

    functional: list[Requirement] = Field(
        ..., min_length=1, description="Functional requirements (FR-xx)"
    )
    non_functional: list[Requirement] = Field(
        ..., min_length=1, description="Non-functional requirements (NFR-xx)"
    )
    acceptance_criteria: Optional[list[str]] = Field(
        None, description="High-level acceptance criteria for the release"
    )
    integrations: Optional[list[Integration]] = Field(
        None, description="External system integrations required"
    )


# ---------------------------------------------------------------------------
# SuccessMetrics section
# ---------------------------------------------------------------------------
class SuccessMetrics(BaseModel):
    """Success metrics — north star + product + guardrails.
    Maps to PRD_SCHEMA.json #/properties/success_metrics.
    """

    model_config = ConfigDict(extra="forbid")

    north_star: str = Field(
        ..., min_length=1, description="The single most important metric for product success"
    )
    product_metrics: list[Metric] = Field(
        ..., min_length=1, description="Core product health metrics"
    )
    guardrail_metrics: Optional[list[Metric]] = Field(
        None, description="Metrics that must NOT degrade (safety rails)"
    )


# ---------------------------------------------------------------------------
# Delivery section
# ---------------------------------------------------------------------------
class Delivery(BaseModel):
    """Delivery planning — priority, timeline confidence, dependencies.
    Maps to PRD_SCHEMA.json #/properties/delivery.
    """

    model_config = ConfigDict(extra="forbid")

    priority: Priority = Field(..., description="Overall delivery priority")
    timeline_confidence: TimelineConfidence = Field(
        ..., description="Confidence level in the proposed timeline"
    )
    target_release: Optional[str] = Field(
        None, description="Target release date or milestone label"
    )
    dependencies: Optional[list[str]] = Field(
        None, description="Blocking dependencies (teams, systems, decisions)"
    )
    team_assumptions: Optional[list[str]] = Field(
        None, description="Assumptions about team size, skills, or availability"
    )


# ---------------------------------------------------------------------------
# ValidationSection section
# ---------------------------------------------------------------------------
class ValidationSection(BaseModel):
    """Validation goals, stakeholders, and simulation requirements.
    Maps to PRD_SCHEMA.json #/properties/validation.

    NOTE: This section defines *what* needs to be validated.
          The actual validation execution is T02/T05 scope.
    """

    model_config = ConfigDict(extra="forbid")

    goals: list[str] = Field(
        ..., min_length=1, description="What we need to learn from the validation run"
    )
    stakeholder_personas: list[Stakeholder] = Field(
        ..., min_length=1, description="Stakeholders who will review the PRD in simulation"
    )
    simulation_requirement: str = Field(
        ...,
        min_length=1,
        description="Minimum simulation fidelity requirement for this PRD",
    )
    validation_templates: Optional[list[ValidationTemplate]] = Field(
        None, description="Predefined MiroFish validation templates to apply"
    )
    must_answer_questions: Optional[list[str]] = Field(
        None, description="Questions that the simulation MUST answer before approval"
    )


# ---------------------------------------------------------------------------
# Artifacts section (optional)
# ---------------------------------------------------------------------------
class Artifacts(BaseModel):
    """Optional rendered and validated artifacts produced from the PRD.
    Maps to PRD_SCHEMA.json #/properties/artifacts.

    NOTE: These are outputs produced by downstream steps (T04, T05).
          Do NOT populate manually during PRD authoring.
    """

    model_config = ConfigDict(extra="forbid")

    prd_markdown: Optional[str] = Field(
        None, description="Rendered PRD as Markdown (produced by T04 renderer)"
    )
    simulation_spec_markdown: Optional[str] = Field(
        None,
        description="Simulation spec document as Markdown (produced by T05 packager)",
    )
    validation_result: Optional[ValidationResult] = Field(
        None, description="MiroFish simulation result (populated after validation run)"
    )


# ---------------------------------------------------------------------------
# PRDDocument — top-level root model
# ---------------------------------------------------------------------------
class PRDDocument(BaseModel):
    """Root PRD document model.

    This is the single source of truth for all downstream steps:
        - Chat orchestration (T03)
        - Markdown rendering (T04)
        - Validation packaging (T05)
        - MiroFish adapter (T06)

    Maps to the root object in PRD_SCHEMA.json.
    schema_version is pinned to Literal["0.1.0"]; bump only with migration plan.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"] = Field(
        ..., description="Locked schema version. Must be '0.1.0'."
    )
    metadata: Metadata
    product: Product
    users: Users
    problem: Problem
    solution: Solution
    scope: Scope
    requirements: Requirements
    success_metrics: SuccessMetrics
    delivery: Delivery
    assumptions: list[TaggedItem] = Field(
        ..., min_length=1, description="Key assumptions the PRD is built on"
    )
    risks: list[Risk] = Field(
        ..., min_length=1, description="Known risks and mitigations"
    )
    open_questions: list[TaggedItem] = Field(
        ..., min_length=1, description="Unresolved questions that must be answered"
    )
    validation: ValidationSection
    artifacts: Optional[Artifacts] = Field(
        None,
        description="Rendered outputs — populated by downstream pipeline, not authors",
    )
