"""
enums.py — All Enum definitions for PRD domain models.

Source of truth: PRD_SCHEMA.json $defs (enum variants)
Dependency: none (leaf module — import nothing from this package)
"""

from enum import Enum


class Language(str, Enum):
    """Supported document languages. Maps to PRD_SCHEMA.json $defs/Language."""

    KO_KR = "ko-KR"
    EN_US = "en-US"


class PrdStatus(str, Enum):
    """Lifecycle status of the PRD document. Maps to PRD_SCHEMA.json $defs/PrdStatus."""

    DISCOVERY = "discovery"
    DRAFTING = "drafting"
    READY_FOR_VALIDATION = "ready_for_validation"
    VALIDATED = "validated"
    REVISING = "revising"
    APPROVED = "approved"


class SourceMode(str, Enum):
    """How the PRD was created. Maps to PRD_SCHEMA.json $defs/SourceMode."""

    CHAT = "chat"
    FORM = "form"
    IMPORT = "import"


class Platform(str, Enum):
    """Target delivery platform(s). Maps to PRD_SCHEMA.json $defs/Platform."""

    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    API = "api"
    INTERNAL_TOOL = "internal_tool"
    AGENT = "agent"
    OTHER = "other"


class ProductStage(str, Enum):
    """Product maturity stage. Maps to PRD_SCHEMA.json $defs/ProductStage."""

    IDEA = "idea"
    MVP = "mvp"
    BETA = "beta"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    """General-purpose priority level for requirements and delivery.
    Maps to PRD_SCHEMA.json $defs/Priority.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    """Risk / assumption severity level. Maps to PRD_SCHEMA.json $defs/Severity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimelineConfidence(str, Enum):
    """Confidence level in the delivery timeline. Maps to PRD_SCHEMA.json $defs/TimelineConfidence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntegrationType(str, Enum):
    """Type of external integration. Maps to PRD_SCHEMA.json $defs/IntegrationType."""

    API = "api"
    WEBHOOK = "webhook"
    SDK = "sdk"
    DATABASE = "database"
    AUTH = "auth"
    PAYMENT = "payment"
    NOTIFICATION = "notification"
    STORAGE = "storage"
    ANALYTICS = "analytics"
    OTHER = "other"


class FeaturePriority(str, Enum):
    """MoSCoW-style feature priority. Maps to PRD_SCHEMA.json $defs/FeaturePriority."""

    MUST_HAVE = "must_have"
    SHOULD_HAVE = "should_have"
    NICE_TO_HAVE = "nice_to_have"
    OUT_OF_SCOPE = "out_of_scope"


class ValidationTemplate(str, Enum):
    """Predefined simulation validation templates. Maps to PRD_SCHEMA.json $defs/ValidationTemplate."""

    STAKEHOLDER_RISK_REVIEW = "stakeholder_risk_review"
    MVP_SCOPE_REVIEW = "mvp_scope_review"
    SECURITY_COMPLIANCE_REVIEW = "security_compliance_review"
    USER_ADOPTION_REVIEW = "user_adoption_review"
    OPERATIONAL_READINESS_REVIEW = "operational_readiness_review"
