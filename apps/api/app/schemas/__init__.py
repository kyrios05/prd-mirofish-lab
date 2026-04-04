"""
schemas/__init__.py — Public re-export of all PRD domain models.

Import pattern for consumers:
    from app.schemas import PRDDocument, Persona, Risk, Language, ...
    from app.schemas import SimulationSpec, ValidationConfig

Dependency order (no cycles):
    enums → common → prd → simulation → __init__
"""

# Enums
from .enums import (
    FeaturePriority,
    IntegrationType,
    Language,
    Platform,
    PrdStatus,
    Priority,
    ProductStage,
    Severity,
    SourceMode,
    TimelineConfidence,
    ValidationTemplate,
)

# Reusable sub-models
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

# Section + top-level models
from .prd import (
    Artifacts,
    Delivery,
    Metadata,
    PRDDocument,
    Problem,
    Product,
    Requirements,
    Scope,
    Solution,
    Source,
    SuccessMetrics,
    Users,
    ValidationSection,
)

# Simulation spec models (T05)
from .simulation import (
    SimulationSpec,
    ValidationConfig,
)

__all__ = [
    # --- Enums ---
    "FeaturePriority",
    "IntegrationType",
    "Language",
    "Platform",
    "PrdStatus",
    "Priority",
    "ProductStage",
    "Severity",
    "SourceMode",
    "TimelineConfidence",
    "ValidationTemplate",
    # --- Sub-models ---
    "Feature",
    "Integration",
    "Metric",
    "Persona",
    "Requirement",
    "Risk",
    "Stakeholder",
    "TaggedItem",
    "ValidationResult",
    # --- Section models ---
    "Artifacts",
    "Delivery",
    "Metadata",
    "Problem",
    "Product",
    "Requirements",
    "Scope",
    "Solution",
    "Source",
    "SuccessMetrics",
    "Users",
    "ValidationSection",
    # --- Root model ---
    "PRDDocument",
    # --- Simulation spec models (T05) ---
    "SimulationSpec",
    "ValidationConfig",
]
