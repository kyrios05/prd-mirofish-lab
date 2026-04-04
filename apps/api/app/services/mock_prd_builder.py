"""
services/mock_prd_builder.py — Deterministic mock PRD section builder.

Purpose
-------
Simulates incremental PRD construction without calling a real LLM.
Each call to build_turn_delta() returns a dict of PRD sections to merge
into the current draft, based on the turn number.

Turn map (1-indexed):
    Turn 1 → metadata, product
    Turn 2 → users, problem
    Turn 3 → solution, scope
    Turn 4 → requirements, success_metrics
    Turn 5 → delivery, assumptions, risks, open_questions, validation
    Turn 6+ → no new sections (all complete)

All returned section dicts are Pydantic-model-validated via model_dump()
so the resulting draft is always T02 validate_prd()-compatible.

Scope guard: NO real LLM calls. This is mock-only until a separate
             LLM integration ticket is implemented.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas import (
    Delivery,
    Feature,
    Metadata,
    Metric,
    Persona,
    Problem,
    Product,
    Requirement,
    Requirements,
    Risk,
    Scope,
    Solution,
    Source,
    Stakeholder,
    SuccessMetrics,
    TaggedItem,
    Users,
    ValidationSection,
)
from app.schemas.enums import (
    FeaturePriority,
    Language,
    Platform,
    PrdStatus,
    Priority,
    ProductStage,
    Severity,
    SourceMode,
    TimelineConfidence,
)


# ---------------------------------------------------------------------------
# Assistant messages per turn
# ---------------------------------------------------------------------------
ASSISTANT_MESSAGES: dict[int, str] = {
    1: (
        "제품의 기본 정보(metadata, product)를 정리했습니다. "
        "다음으로 타겟 사용자와 해결할 문제를 알려주세요."
    ),
    2: (
        "사용자 페르소나와 핵심 문제(users, problem)를 정의했습니다. "
        "어떤 솔루션과 MVP 범위를 생각하고 계신가요?"
    ),
    3: (
        "솔루션과 MVP 범위(solution, scope)를 정리했습니다. "
        "기능/비기능 요구사항과 성공 지표를 구체화해볼까요?"
    ),
    4: (
        "요구사항과 성공 지표(requirements, success_metrics)를 작성했습니다. "
        "배포 계획, 가정, 리스크, 미결 사항, 검증 계획을 확인해주세요."
    ),
    5: (
        "PRD 초안이 완성되었습니다! 모든 섹션이 채워졌습니다. "
        "검증을 시작하려면 /validation/run을 호출하세요."
    ),
}

FALLBACK_MESSAGE = (
    "모든 PRD 섹션이 이미 채워져 있습니다. "
    "내용을 수정하거나 /validation/run으로 검증을 진행하세요."
)


# ---------------------------------------------------------------------------
# Section builders — each returns a validated dict fragment
# ---------------------------------------------------------------------------

def _build_metadata(session_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return Metadata(
        project_id=f"proj-{session_id[:8]}",
        created_at=now,
        updated_at=now,
        language=Language.KO_KR,
        status=PrdStatus.DRAFTING,
        source=Source(
            mode=SourceMode.CHAT,
            session_id=session_id,
            chat_turn_count=1,
        ),
        owner="mock-user",
        version="0.1.0-draft",
    ).model_dump()


def _build_product() -> dict[str, Any]:
    return Product(
        name="[Mock] 제품명",
        one_liner="채팅으로 PRD를 생성하고 시뮬레이션으로 검증하는 시스템",
        category="AI Developer Tool",
        platforms=[Platform.WEB, Platform.API],
        stage=ProductStage.MVP,
        industry_context=["B2B SaaS", "제품 기획 도구"],
        domain_context="LLM 기반 구조화 문서 생성",
    ).model_dump()


def _build_users() -> dict[str, Any]:
    return Users(
        primary_personas=[
            Persona(
                name="PM 김지수",
                role="Product Manager",
                goals=["빠르게 PRD 초안을 작성한다", "이해관계자 리뷰를 통과한다"],
                pain_points=["PRD 작성에 3-5일이 소요된다", "구조화된 형식 유지가 어렵다"],
                company_type="Series B 스타트업",
                context="주당 2-3개 PRD를 작성하는 시니어 PM",
            )
        ],
        non_targets=["개인 개발자 (팀 협업 니즈 없음)"],
    ).model_dump()


def _build_problem() -> dict[str, Any]:
    return Problem(
        core_problem="PM이 구조화된 PRD를 작성하는 데 과도한 시간을 소비한다.",
        pain_points=[
            "빈 문서에서 시작하는 인지적 부담",
            "섹션 간 일관성 유지 어려움",
            "이해관계자 리뷰 전 품질 확인 불가",
        ],
        current_alternatives=[
            "Notion/Confluence 템플릿 수동 작성",
            "ChatGPT로 자유 형식 생성 (구조 보장 없음)",
        ],
        why_now="LLM 성능이 구조화된 JSON 추출에 충분한 수준에 도달했다.",
        jobs_to_be_done=["제품 아이디어를 실행 가능한 문서로 변환해라"],
    ).model_dump()


def _build_solution() -> dict[str, Any]:
    return Solution(
        summary="채팅 인터페이스로 PRD를 점진적으로 구축하고 시뮬레이션으로 검증한다.",
        value_proposition="대화만으로 구조화된 PRD를 30분 내에 완성할 수 있다.",
        key_features=[
            Feature(
                name="Chat-driven PRD 생성",
                description="LLM 기반 대화로 PRD 섹션을 점진적으로 채운다.",
                priority=FeaturePriority.MUST_HAVE,
                rationale="핵심 가치 제안의 직접 구현",
            ),
            Feature(
                name="PRD Markdown 렌더링",
                description="완성된 PRD를 Markdown 문서로 렌더링한다.",
                priority=FeaturePriority.MUST_HAVE,
                rationale="팀 공유 및 이해관계자 전달에 필수",
            ),
        ],
        user_journey=[
            "1. 제품 아이디어를 채팅으로 입력",
            "2. 시스템이 PRD 섹션을 순서대로 질문/채움",
            "3. 완성된 PRD를 Markdown으로 확인",
            "4. MiroFish 검증 트리거",
        ],
    ).model_dump()


def _build_scope() -> dict[str, Any]:
    return Scope(
        mvp_in_scope=[
            "Chat 기반 PRD 섹션 입력 (14개 섹션)",
            "PRDDocument JSON 구조화 저장",
            "PRD Markdown 렌더링",
        ],
        out_of_scope=[
            "멀티 사용자 실시간 협업 편집",
            "PRD 버전 히스토리",
            "외부 Jira/Linear 연동",
        ],
        future_expansion=["팀 워크스페이스 (V2)", "PRD → Jira Epic 자동 생성 (V2)"],
        launch_constraints=["MiroFish API 연동 계약 완료 전까지 Mock 모드 사용"],
    ).model_dump()


def _build_requirements() -> dict[str, Any]:
    return Requirements(
        functional=[
            Requirement(
                id="FR-01",
                statement="사용자는 채팅 메시지를 통해 PRD의 모든 required 섹션을 입력할 수 있어야 한다.",
                priority=Priority.CRITICAL,
            ),
            Requirement(
                id="FR-02",
                statement="시스템은 각 채팅 메시지에서 구조화된 PRD 데이터를 추출하여 업데이트해야 한다.",
                priority=Priority.CRITICAL,
            ),
        ],
        non_functional=[
            Requirement(
                id="NFR-01",
                statement="채팅 API 응답 시간은 p95 기준 3초 이내여야 한다.",
                priority=Priority.HIGH,
            ),
            Requirement(
                id="NFR-02",
                statement="PRD JSON은 PRD_SCHEMA.json 스키마를 항상 준수해야 한다.",
                priority=Priority.CRITICAL,
            ),
        ],
        acceptance_criteria=["PRD_SCHEMA.json의 모든 required 섹션이 채팅으로 입력 가능함"],
    ).model_dump()


def _build_success_metrics() -> dict[str, Any]:
    return SuccessMetrics(
        north_star="PRD 완성 후 첫 이해관계자 리뷰 통과율 (목표: 80% 이상)",
        product_metrics=[
            Metric(
                name="PRD 초안 완성 시간",
                target="30분 이내",
                timeframe="런치 후 1개월",
            ),
        ],
        guardrail_metrics=[
            Metric(
                name="PRD 스키마 검증 실패율",
                target="0.1% 미만",
                timeframe="항상",
            ),
        ],
    ).model_dump()


def _build_delivery() -> dict[str, Any]:
    return Delivery(
        priority=Priority.CRITICAL,
        timeline_confidence=TimelineConfidence.MEDIUM,
        target_release="2026-06-01",
        dependencies=["MiroFish API 연동 계약 완료", "OpenAI-compatible API 키 발급"],
        team_assumptions=["백엔드 1명, 프론트엔드 1명, PM 1명으로 구성"],
    ).model_dump()


def _build_assumptions() -> list[dict[str, Any]]:
    return [
        TaggedItem(text="PM은 채팅 인터페이스에 익숙하다.", tag="user", severity=Severity.MEDIUM).model_dump(),
        TaggedItem(text="LLM은 PRD 구조를 90% 이상 정확도로 추출할 수 있다.", tag="technical", severity=Severity.CRITICAL).model_dump(),
    ]


def _build_risks() -> list[dict[str, Any]]:
    return [
        Risk(
            title="LLM 응답 품질 불안정",
            description="LLM이 PRD 구조를 일관되게 추출하지 못할 수 있다.",
            severity=Severity.HIGH,
            mitigation="Few-shot prompting + JSON mode 강제 + Pydantic 재검증 루프",
            owner="Backend Engineer",
        ).model_dump(),
    ]


def _build_open_questions() -> list[dict[str, Any]]:
    return [
        TaggedItem(text="MiroFish API의 응답 SLA는 동기/비동기 중 어떤 방식인가?", tag="technical", severity=Severity.HIGH).model_dump(),
    ]


def _build_validation(session_id: str) -> dict[str, Any]:
    return ValidationSection(
        goals=["MVP 범위가 6주 내 구현 가능한지 확인한다"],
        stakeholder_personas=[
            Stakeholder(
                name="Engineering Lead",
                role="Engineering Lead",
                review_angle="기술적 실현 가능성 및 리소스 요구사항 검토",
                likely_objections=["MiroFish 문서 없이 T05 범위를 확정할 수 없음"],
            )
        ],
        simulation_requirement="최소 2개 이상의 이해관계자 시뮬레이션 완료",
    ).model_dump()


# ---------------------------------------------------------------------------
# Turn map
# ---------------------------------------------------------------------------
def build_turn_delta(
    turn_number: int, session_id: str
) -> tuple[dict[str, Any], str]:
    """
    Return (section_dict_to_merge, assistant_message) for the given turn.

    Parameters
    ----------
    turn_number : int    1-indexed turn count (after this message is processed).
    session_id  : str    Used for metadata project_id / session_id fields.

    Returns
    -------
    (delta, message)
    delta   – dict of section_name → section_value to merge into current draft.
    message – assistant reply text.
    """
    if turn_number == 1:
        delta = {
            "metadata": _build_metadata(session_id),
            "product": _build_product(),
        }
    elif turn_number == 2:
        delta = {
            "users": _build_users(),
            "problem": _build_problem(),
        }
    elif turn_number == 3:
        delta = {
            "solution": _build_solution(),
            "scope": _build_scope(),
        }
    elif turn_number == 4:
        delta = {
            "requirements": _build_requirements(),
            "success_metrics": _build_success_metrics(),
        }
    elif turn_number == 5:
        delta = {
            "delivery": _build_delivery(),
            "assumptions": _build_assumptions(),
            "risks": _build_risks(),
            "open_questions": _build_open_questions(),
            "validation": _build_validation(session_id),
        }
    else:
        delta = {}

    message = ASSISTANT_MESSAGES.get(turn_number, FALLBACK_MESSAGE)
    return delta, message
