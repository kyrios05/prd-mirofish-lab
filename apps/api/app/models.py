"""
models.py — Explicit re-exports from app.schemas.

T01 originally created this file as a ``from app.schemas import *`` shim.
T03 replaces the wildcard with explicit named imports to restore IDE
auto-completion and eliminate the hidden dependency surface.

All routes and services SHOULD import directly from ``app.schemas``.
This module exists only for any third-party code that may still reference
``app.models`` — it will be removed in a future cleanup ticket.
"""

from app.schemas import (  # noqa: F401
    # Enums
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
    # Sub-models (common)
    Feature,
    Integration,
    Metric,
    Persona,
    Requirement,
    Risk,
    Stakeholder,
    TaggedItem,
    ValidationResult,
    # Section models (prd)
    Artifacts,
    Delivery,
    Metadata,
    Problem,
    Product,
    Requirements,
    Scope,
    Solution,
    Source,
    SuccessMetrics,
    Users,
    ValidationSection,
    # Root document
    PRDDocument,
)

__all__ = [
    # Enums
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
    # Sub-models
    "Feature",
    "Integration",
    "Metric",
    "Persona",
    "Requirement",
    "Risk",
    "Stakeholder",
    "TaggedItem",
    "ValidationResult",
    # Section models
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
    # Root
    "PRDDocument",
]
