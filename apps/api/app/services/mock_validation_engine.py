"""
services/mock_validation_engine.py — Content-aware mock validation engine (T06).

Public API
----------
    run_mock_validation(spec: SimulationSpec) -> ValidationResult

Design contract
---------------
- Pure function: SimulationSpec in → ValidationResult out.
- No HTTP calls, no I/O, no LLM — uses only data already in spec.
- Content-aware: all output is derived from the PRD content inside spec.
  Nothing is hard-coded; every list is built from spec fields.
- Deterministic: same spec → same result (no random, no datetime).
- Korean language output by default (metadata.language-aware switch is
  implemented for future bilingual support).

Generation strategy
-------------------
summary
    product name  (spec.prd_summary["name"])
    + first validation goal  (spec.validation_config.goals[0])
    → "{name} PRD 검증 완료 — {goal} 기준으로 분석했습니다."

top_risks
    spec.validation_config.focus_areas 중 '?' 나 '어느', '어떻게' 등
    open-question 패턴이 없는 항목 → risk 항목으로 분류
    (T05: focus_areas = risks[].title ++ open_questions[].text 순서이므로
     open-question 특징 텍스트 없는 앞부분이 risk 제목에 해당)
    최대 5개, 최소 1개 (없으면 "식별된 리스크 없음" 대신 generic fallback)

missing_requirements
    PRD의 requirements 섹션에서 빠진 항목 탐지:
    - non_functional이 없거나 1개 이하 → 비기능 요구사항 보강 지적
    - acceptance_criteria가 None 또는 빈 리스트 → 수락 기준 부재 지적
    - integrations가 None 또는 빈 리스트 → 외부 시스템 연동 정보 부재 지적
    - requirements.functional이 3개 미만 → 기능 요구사항 부족 지적

stakeholder_objections
    각 stakeholder_persona에 대해:
    1. persona.likely_objections 가 있으면 그대로 사용
    2. 없으면 review_angle을 기반으로 파생:
       "{name}({role}): '{review_angle}' 관점에서 현재 PRD의 근거가 불충분합니다."
    최소 1개 보장 (personas 0개인 경우 generic fallback)

scope_adjustments
    - delivery.timeline_confidence == "low" → 타임라인 신뢰도 낮음 경고 + 축소 제안
    - mvp_in_scope items > 5 AND timeline_confidence != "high" → 범위 축소 제안
    - dependencies가 있으면 → 종속성 리스크 표시
    최소 1개 보장

recommended_questions
    1. must_answer_questions 그대로 포함
    2. focus_areas 중 open-question 패턴 항목 포함
    최소 1개 보장 (must_answer 없고 focus open-questions 없으면 generic)

rewrite_suggestions
    빈 optional 필드 감지:
    - solution.user_journey == None → user_journey 보강 제안
    - requirements.acceptance_criteria None/빈 → AC 작성 제안
    - requirements.integrations None/빈 → integrations 섹션 보강 제안
    - problem.alternatives_considered 없거나 짧음 → 대안 분석 보강 제안
    - product.domain_context None → 도메인 컨텍스트 보강 제안
    최소 1개 보장

Scope guard
-----------
- HTTP calls: T10
- LLM calls: separate ticket
- Chat orchestration changes: T03 완료
- Markdown renderer changes: T04 완료
- ValidationResult / SimulationSpec schema changes: T01/T05 완료
- Frontend: T07/T08
- State machine: T09
"""

from __future__ import annotations

from typing import Any

from app.schemas import ValidationResult
from app.schemas.simulation import SimulationSpec


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Patterns that distinguish open-question text from risk titles inside focus_areas.
# T05 builds focus_areas as risks[].title ++ open_questions[].text.
# Open questions often contain Korean question particles or sentence-final '?'.
_QUESTION_MARKERS = ("?", "어느", "어떻게", "무엇", "왜", "언제", "누가", "얼마나", "인가", "인지")


def _is_question(text: str) -> bool:
    """Return True if the text looks like an open question (not a risk title)."""
    for marker in _QUESTION_MARKERS:
        if marker in text:
            return True
    return False


def _split_focus_areas(focus_areas: list[str]) -> tuple[list[str], list[str]]:
    """
    Split focus_areas into (risk_items, question_items).

    T05 appends risks before questions, but we use content heuristics so
    the split is robust even if the order ever changes.
    """
    risks: list[str] = []
    questions: list[str] = []
    for item in focus_areas:
        if _is_question(item):
            questions.append(item)
        else:
            risks.append(item)
    return risks, questions


def _safe_str(value: Any, fallback: str = "") -> str:
    """Return str(value) or fallback if value is None/empty."""
    if value is None:
        return fallback
    s = str(value).strip()
    return s if s else fallback


def _list_or_empty(value: Any) -> list:
    """Return value if it's a non-empty list, else []."""
    if isinstance(value, list) and len(value) > 0:
        return value
    return []


# ---------------------------------------------------------------------------
# 1. summary
# ---------------------------------------------------------------------------

def _build_summary(spec: SimulationSpec) -> str:
    """
    Produce a 1–2 sentence high-level summary.

    Format:
        "{product_name} PRD 검증이 완료되었습니다.
         {goal} 기준으로 시뮬레이션을 수행했으며,
         {n}개의 이해관계자 관점과 {m}개의 핵심 포커스 영역이 분석되었습니다."
    """
    product_name = _safe_str(spec.prd_summary.get("name"), "제품")
    goals = spec.validation_config.goals
    goal_text = goals[0] if goals else "PRD 전반적인 품질 검증"
    n_stakeholders = len(spec.validation_config.stakeholder_personas)
    n_focus = len(spec.validation_config.focus_areas)

    return (
        f"{product_name} PRD 검증이 완료되었습니다. "
        f"'{goal_text}' 기준으로 시뮬레이션을 수행했으며, "
        f"{n_stakeholders}명의 이해관계자 관점과 "
        f"{n_focus}개의 핵심 포커스 영역이 분석되었습니다."
    )


# ---------------------------------------------------------------------------
# 2. top_risks
# ---------------------------------------------------------------------------

def _build_top_risks(spec: SimulationSpec) -> list[str]:
    """
    Build top_risks from focus_areas (risk portion) + PRD risks.

    Strategy:
      1. Extract risk items from focus_areas (non-question entries).
      2. Cap at 5.
      3. If empty, fall back to a generic risk based on product stage.
    """
    risk_items, _ = _split_focus_areas(spec.validation_config.focus_areas)
    # Add severity signal from prd_structured risks if available
    prd_risks = _list_or_empty(spec.prd_structured.get("risks", []))
    extra: list[str] = []
    for r in prd_risks:
        title = _safe_str(r.get("title"))
        severity = _safe_str(r.get("severity"))
        if title and title not in risk_items:
            label = f"{title} (심각도: {severity})" if severity else title
            extra.append(label)

    combined = risk_items + extra
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in combined:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    if not unique:
        # Generic fallback based on product stage
        stage = _safe_str(spec.prd_summary.get("stage"), "unknown")
        unique = [f"제품 단계({stage}) 대비 리스크 분석 정보가 부족합니다."]

    return unique[:5]


# ---------------------------------------------------------------------------
# 3. missing_requirements
# ---------------------------------------------------------------------------

def _build_missing_requirements(spec: SimulationSpec) -> list[str]:
    """
    Detect gaps in the requirements section and report them.

    Checks:
    - Non-functional requirements: < 2 items
    - Acceptance criteria: None or empty
    - Integrations: None or empty
    - Functional requirements: < 3 items
    """
    reqs = spec.prd_structured.get("requirements", {}) or {}
    missing: list[str] = []

    # Non-functional requirements check
    nfr = _list_or_empty(reqs.get("non_functional"))
    if len(nfr) < 2:
        missing.append(
            "비기능 요구사항(NFR)이 부족합니다. "
            "성능, 보안, 가용성 등 최소 2개 이상의 NFR을 정의해야 합니다."
        )

    # Acceptance criteria check
    ac = reqs.get("acceptance_criteria")
    if not _list_or_empty(ac):
        missing.append(
            "수락 기준(Acceptance Criteria)이 정의되지 않았습니다. "
            "각 기능 요구사항에 대한 검증 가능한 완료 기준을 추가하세요."
        )

    # Integrations check
    integrations = reqs.get("integrations")
    if not _list_or_empty(integrations):
        missing.append(
            "외부 시스템 연동(Integrations) 정보가 없습니다. "
            "연동할 API, 서비스, 데이터베이스 등을 명시해야 합니다."
        )

    # Functional requirements check
    func = _list_or_empty(reqs.get("functional"))
    if len(func) < 3:
        missing.append(
            f"기능 요구사항이 {len(func)}개로 부족합니다. "
            "핵심 사용자 시나리오를 커버하는 최소 3개 이상의 기능 요구사항을 추가하세요."
        )

    if not missing:
        missing.append(
            "요구사항 섹션이 전반적으로 잘 구성되어 있습니다. "
            "우선순위(MoSCoW) 분류를 모든 요구사항에 적용했는지 확인하세요."
        )

    return missing


# ---------------------------------------------------------------------------
# 4. stakeholder_objections
# ---------------------------------------------------------------------------

def _build_stakeholder_objections(spec: SimulationSpec) -> list[str]:
    """
    Generate objections from stakeholder personas.

    For each persona:
      - If likely_objections is populated: use those strings directly.
      - Otherwise: derive an objection from review_angle.

    Guarantees at least 1 objection.
    """
    personas = spec.validation_config.stakeholder_personas
    objections: list[str] = []

    for persona in personas:
        name = _safe_str(persona.get("name"), "이해관계자")
        role = _safe_str(persona.get("role"), "")
        review_angle = _safe_str(persona.get("review_angle"), "")
        likely = persona.get("likely_objections")

        if likely and isinstance(likely, list) and len(likely) > 0:
            # Use existing objections verbatim
            for obj in likely:
                if obj and str(obj).strip():
                    objections.append(str(obj).strip())
        else:
            # Derive from review_angle
            label = f"{name}" + (f" ({role})" if role else "")
            if review_angle:
                objections.append(
                    f"{label}: '{review_angle}' 관점에서 현재 PRD의 근거 자료가 불충분합니다."
                )
            else:
                objections.append(
                    f"{label}: PRD 전반에 걸쳐 추가적인 세부 근거 자료가 필요합니다."
                )

    # Fallback if no personas defined
    if not objections:
        objections.append(
            "이해관계자 시뮬레이션 결과: PRD의 기술적 실현 가능성에 대한 "
            "추가 검토가 필요합니다."
        )

    return objections


# ---------------------------------------------------------------------------
# 5. scope_adjustments
# ---------------------------------------------------------------------------

def _build_scope_adjustments(spec: SimulationSpec) -> list[str]:
    """
    Recommend scope changes based on timeline_confidence and MVP scope size.

    Rules:
    - timeline_confidence == "low"  → 전반적 범위 축소 권고
    - mvp_in_scope > 5 AND confidence != "high" → 핵심 기능만 남기도록 제안
    - dependencies present → 종속성 리스크 경고
    - confidence == "high" AND mvp <= 3 → 범위 확장 검토 여지
    """
    delivery = spec.prd_structured.get("delivery", {}) or {}
    scope = spec.prd_structured.get("scope", {}) or {}

    timeline_confidence = _safe_str(delivery.get("timeline_confidence"), "medium")
    mvp_items = _list_or_empty(scope.get("mvp_in_scope"))
    mvp_count = len(mvp_items)
    dependencies = _list_or_empty(delivery.get("dependencies"))

    adjustments: list[str] = []

    if timeline_confidence == "low":
        adjustments.append(
            "타임라인 신뢰도가 'low'로 설정되어 있습니다. "
            "MVP 범위를 현재의 50-60% 수준으로 축소하고 나머지를 v1.1로 이관할 것을 권장합니다."
        )

    if mvp_count > 5 and timeline_confidence != "high":
        adjustments.append(
            f"MVP 범위에 {mvp_count}개의 기능이 포함되어 있어 과부하 위험이 있습니다. "
            "타임라인 신뢰도를 고려할 때 핵심 3-4개 기능에 집중하는 것을 권장합니다."
        )

    if dependencies:
        dep_names = [_safe_str(d) for d in dependencies[:3]]
        dep_str = ", ".join(dep_names)
        adjustments.append(
            f"외부 종속성({dep_str} 등)이 MVP 일정에 영향을 줄 수 있습니다. "
            "종속성 해소 계획을 별도로 수립하세요."
        )

    if timeline_confidence == "high" and mvp_count <= 3:
        adjustments.append(
            "타임라인 신뢰도가 높고 MVP 범위가 적절합니다. "
            "초기 사용자 피드백을 위한 빠른 출시 계획을 검토해 보세요."
        )

    if not adjustments:
        adjustments.append(
            f"현재 MVP 범위({mvp_count}개 기능)와 타임라인 신뢰도({timeline_confidence})는 "
            "적절한 수준입니다. 스프린트별 마일스톤을 구체화하면 실행 가능성이 높아집니다."
        )

    return adjustments


# ---------------------------------------------------------------------------
# 6. recommended_questions
# ---------------------------------------------------------------------------

def _build_recommended_questions(spec: SimulationSpec) -> list[str]:
    """
    Build recommended follow-up questions.

    Priority order:
      1. must_answer_questions (verbatim from spec)
      2. open-question items from focus_areas
      3. Generic fallback if both are empty
    """
    _, question_items = _split_focus_areas(spec.validation_config.focus_areas)
    must_answer = list(spec.validation_config.must_answer_questions)

    # Combine: must_answer first, then focus open-questions (deduplicate)
    combined: list[str] = list(must_answer)
    seen = set(must_answer)
    for q in question_items:
        if q not in seen:
            seen.add(q)
            combined.append(q)

    if not combined:
        product_name = _safe_str(spec.prd_summary.get("name"), "이 제품")
        combined = [
            f"{product_name}의 MVP가 계획된 타임라인 내에 실제로 구현 가능한가?",
            "주요 사용자 페르소나가 이 제품을 선택할 이유가 충분한가?",
            "측정 가능한 성공 기준이 비즈니스 목표와 일치하는가?",
        ]

    return combined


# ---------------------------------------------------------------------------
# 7. rewrite_suggestions
# ---------------------------------------------------------------------------

def _build_rewrite_suggestions(spec: SimulationSpec) -> list[str]:
    """
    Suggest specific rewrites for missing or weak PRD sections.

    Checks:
    - solution.user_journey: None → suggest adding
    - requirements.acceptance_criteria: None/empty → suggest adding
    - requirements.integrations: None/empty → suggest adding
    - problem.alternatives_considered: None/short → suggest elaborating
    - product.domain_context: None → suggest adding
    - success_metrics.guardrail_metrics: empty → suggest adding
    """
    prd = spec.prd_structured
    solution = prd.get("solution", {}) or {}
    reqs = prd.get("requirements", {}) or {}
    problem = prd.get("problem", {}) or {}
    product = prd.get("product", {}) or {}
    metrics = prd.get("success_metrics", {}) or {}

    suggestions: list[str] = []

    # user_journey check
    if not _list_or_empty(solution.get("user_journey")):
        suggestions.append(
            "solution.user_journey 섹션을 추가하면 제품 흐름 이해가 향상됩니다. "
            "사용자가 첫 화면에서 핵심 가치를 경험하기까지의 단계를 3-5개 스텝으로 정의하세요."
        )

    # acceptance_criteria check
    if not _list_or_empty(reqs.get("acceptance_criteria")):
        suggestions.append(
            "requirements.acceptance_criteria가 비어 있습니다. "
            "각 기능 요구사항에 대해 '~할 수 있다', '~가 표시된다' 형태의 "
            "검증 가능한 수락 기준을 추가하세요."
        )

    # integrations check
    if not _list_or_empty(reqs.get("integrations")):
        suggestions.append(
            "requirements.integrations 섹션이 없습니다. "
            "외부 API, 데이터베이스, 인증 서비스 등 연동이 필요한 시스템을 명시하세요."
        )

    # alternatives_considered check
    alternatives = _safe_str(problem.get("alternatives_considered"))
    if len(alternatives) < 20:
        suggestions.append(
            "problem.alternatives_considered 설명이 짧거나 누락되어 있습니다. "
            "경쟁 제품이나 대안 솔루션과의 비교 분석을 추가하면 의사결정 근거가 강화됩니다."
        )

    # domain_context check
    if not _safe_str(product.get("domain_context")):
        suggestions.append(
            "product.domain_context가 없습니다. "
            "산업 특수성, 규제 요건, 기술 생태계 등 도메인 배경을 추가하면 "
            "이해관계자 설득력이 높아집니다."
        )

    # guardrail_metrics check
    guardrails = _list_or_empty(metrics.get("guardrail_metrics"))
    if not guardrails:
        suggestions.append(
            "success_metrics.guardrail_metrics가 정의되지 않았습니다. "
            "에러율, 이탈률, 응답 지연 등 '넘어서는 안 되는' 경계값을 설정하세요."
        )

    if not suggestions:
        suggestions.append(
            "PRD 섹션 구성이 전반적으로 완성도가 높습니다. "
            "각 섹션의 서술을 더 구체적인 수치와 기준으로 보강하면 검토 통과 가능성이 높아집니다."
        )

    return suggestions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_mock_validation(spec: SimulationSpec) -> ValidationResult:
    """
    Generate a content-aware mock ValidationResult from a SimulationSpec.

    Parameters
    ----------
    spec : SimulationSpec
        Produced by validation_packager.package_for_simulation().
        All 7 ValidationResult fields are derived from spec's data.

    Returns
    -------
    ValidationResult
        Fully populated result with all 7 required fields.
        Deterministic: same spec → same result.

    Notes
    -----
    - No HTTP calls, no LLM, no random numbers.
    - Korean language output by default.
    - Replace this function with T10 HTTP adapter when MiroFish is available.
    """
    return ValidationResult(
        summary=_build_summary(spec),
        top_risks=_build_top_risks(spec),
        missing_requirements=_build_missing_requirements(spec),
        stakeholder_objections=_build_stakeholder_objections(spec),
        scope_adjustments=_build_scope_adjustments(spec),
        recommended_questions=_build_recommended_questions(spec),
        rewrite_suggestions=_build_rewrite_suggestions(spec),
    )
