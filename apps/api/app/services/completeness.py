"""
services/completeness.py — PRD section completeness calculator.

Computes which of the 14 required PRD sections are filled,
which are missing, the overall progress ratio, and the draft_status
label derived from that ratio.

The 14 required sections come directly from PRD_SCHEMA.json top-level
"required" array (excluding "schema_version" which is a constant,
not a content section):

    metadata, product, users, problem, solution, scope, requirements,
    success_metrics, delivery, assumptions, risks, open_questions, validation

Array sections (assumptions, risks, open_questions) are counted as
"filled" when the list is non-empty.

Scope guard: no rendering, no validation packager — pure calculation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Constants — matches PRD_SCHEMA.json top-level required (content sections)
# ---------------------------------------------------------------------------
REQUIRED_SECTIONS: list[str] = [
    "metadata",
    "product",
    "users",
    "problem",
    "solution",
    "scope",
    "requirements",
    "success_metrics",
    "delivery",
    "assumptions",
    "risks",
    "open_questions",
    "validation",
]

TOTAL_SECTIONS: int = len(REQUIRED_SECTIONS)  # 13 content sections


# ---------------------------------------------------------------------------
# DraftStatus
# ---------------------------------------------------------------------------
class DraftStatus:
    EMPTY = "empty"
    INCOMPLETE = "incomplete"
    READY_FOR_VALIDATION = "ready_for_validation"


# ---------------------------------------------------------------------------
# CompletenessResult
# ---------------------------------------------------------------------------
@dataclass
class CompletenessResult:
    """
    Result of a completeness calculation.

    Attributes
    ----------
    filled:       Sections present and non-empty in the draft.
    missing:      Sections absent or empty in the draft.
    progress:     Ratio of filled / TOTAL_SECTIONS  (0.0 – 1.0).
    draft_status: "empty" | "incomplete" | "ready_for_validation"
    """

    filled: list[str]
    missing: list[str]
    progress: float
    draft_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "filled": self.filled,
            "missing": self.missing,
            "progress": round(self.progress, 4),
            "draft_status": self.draft_status,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def calculate_completeness(prd_draft: dict[str, Any] | None) -> CompletenessResult:
    """
    Calculate the completeness of a partial PRD draft dict.

    Parameters
    ----------
    prd_draft : dict | None
        A dict that is the output of PRDDocument.model_dump(), or None.
        Partial drafts (missing keys) are accepted.

    Returns
    -------
    CompletenessResult
        filled / missing section names, progress ratio, draft_status.
    """
    if not prd_draft:
        return CompletenessResult(
            filled=[],
            missing=list(REQUIRED_SECTIONS),
            progress=0.0,
            draft_status=DraftStatus.EMPTY,
        )

    filled: list[str] = []
    missing: list[str] = []

    for section in REQUIRED_SECTIONS:
        value = prd_draft.get(section)
        if _is_filled(section, value):
            filled.append(section)
        else:
            missing.append(section)

    progress = len(filled) / TOTAL_SECTIONS

    if progress == 0.0:
        status = DraftStatus.EMPTY
    elif progress < 1.0:
        status = DraftStatus.INCOMPLETE
    else:
        status = DraftStatus.READY_FOR_VALIDATION

    return CompletenessResult(
        filled=filled,
        missing=missing,
        progress=progress,
        draft_status=status,
    )


def _is_filled(section: str, value: Any) -> bool:
    """
    Determine whether a section value counts as 'filled'.

    Rules:
    - None → not filled
    - list  → filled iff len >= 1
    - dict  → filled iff non-empty
    - str   → filled iff len >= 1
    - other → filled if truthy
    """
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) >= 1
    if isinstance(value, dict):
        return len(value) >= 1
    if isinstance(value, str):
        return len(value) >= 1
    return bool(value)


# ---------------------------------------------------------------------------
# Question suggestions
# ---------------------------------------------------------------------------
_SECTION_QUESTIONS: dict[str, str] = {
    "metadata":        "이 PRD의 프로젝트 ID, 작성 날짜, 언어, 상태를 알려주세요.",
    "product":         "제품 이름, 한 줄 설명, 카테고리, 플랫폼, 현재 단계를 알려주세요.",
    "users":           "주요 타겟 사용자(페르소나)의 이름, 역할, 목표, 페인포인트를 설명해주세요.",
    "problem":         "이 제품이 해결하는 핵심 문제와 현재 대안을 설명해주세요.",
    "solution":        "솔루션 요약, 가치 제안, 핵심 기능(MoSCoW 우선순위 포함)을 알려주세요.",
    "scope":           "MVP에 포함되는 것과 제외되는 것의 범위를 명확히 해주세요.",
    "requirements":    "기능 요구사항(FR)과 비기능 요구사항(NFR)을 ID와 함께 작성해주세요.",
    "success_metrics": "북극성 지표(North Star)와 핵심 제품 지표를 알려주세요.",
    "delivery":        "배포 우선순위, 타임라인 신뢰도, 목표 출시일을 알려주세요.",
    "assumptions":     "PRD 작성의 전제가 되는 가정들을 나열해주세요.",
    "risks":           "주요 리스크(제목, 설명, 심각도)와 완화 방법을 설명해주세요.",
    "open_questions":  "아직 결정되지 않은 미결 질문들을 나열해주세요.",
    "validation":      "검증 목표, 이해관계자 페르소나, 시뮬레이션 요구사항을 정의해주세요.",
}


def suggest_next_questions(missing_sections: list[str], max_count: int = 3) -> list[str]:
    """Return question strings for the first `max_count` missing sections."""
    return [
        _SECTION_QUESTIONS[s]
        for s in missing_sections[:max_count]
        if s in _SECTION_QUESTIONS
    ]
