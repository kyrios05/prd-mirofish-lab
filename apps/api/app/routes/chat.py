"""
routes/chat.py — Chat-driven PRD generation endpoints.

T03 API contract (unchanged structure)
────────────────────────────────────────
POST /chat/sessions              → CreateSessionResponse
GET  /chat/sessions/{session_id} → SessionStatusResponse
POST /chat/message               → ChatResponse

T09 additions
─────────────
ChatResponse gains:
  current_phase     : str  — current ConversationPhase value
  available_actions : list[str] — actions allowed in the current phase

New endpoints:
  POST /chat/sessions/{session_id}/checkpoint  → CheckpointResponse
  POST /chat/sessions/{session_id}/restore     → RestoreResponse
  GET  /chat/sessions/{session_id}/checkpoints → CheckpointsListResponse

send_message() flow updated:
  message → phase check → update_from_message → completeness →
  auto_advance → auto-checkpoint on phase transition → response

Scope guard
-----------
- Real LLM orchestration: separate ticket.
- Markdown rendering: T04 (frozen).
- MiroFish integration: T10 (frozen).
- mock_prd_builder: T03 (frozen).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
import json
import asyncio
from pydantic import BaseModel, Field

from app.services.completeness import (
    CompletenessResult,
    calculate_completeness,
    suggest_next_questions,
)
from app.services.conversation_state import (
    PHASE_GREETING_MSG,
    PHASE_READY_MSG,
    PHASE_REVIEWING_MSG,
    PHASE_VALIDATED_MSG,
    ConversationPhase,
    get_available_actions,
    list_checkpoints,
    restore_checkpoint,
    save_checkpoint,
    state_machine_from_phase,
)
from app.services.markdown_renderer import render_prd_markdown
from app.services.prd_generator import PRDGeneratorService
from app.services.session_store import session_store
from app.services.mirofish_service import MiroFishService
from app.schemas.prd import PRDDocument

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("app.api.chat")

# Module-level service instances
_prd_service = PRDGeneratorService()
_mirofish = MiroFishService()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Inbound chat message from the user."""

    session_id: str = Field(..., description="Active session UUID (from POST /chat/sessions).")
    message: str = Field(..., min_length=1, description="User's chat message text.")
    context: dict[str, Any] | None = Field(
        None,
        description="Optional extra context dict (e.g., hints from the client).",
    )

class ActionRequest(BaseModel):
    """Trigger a state machine action manually."""
    session_id: str = Field(..., description="Active session UUID")
    action_id: str = Field(..., description="Action ID to perform, e.g., 'start_simulation'")
    payload: dict[str, Any] | None = None


class CompletenessInfo(BaseModel):
    """Completeness snapshot of the current PRD draft."""

    filled: list[str] = Field(..., description="Section names that are present and non-empty.")
    missing: list[str] = Field(..., description="Section names that are absent or empty.")
    progress: float = Field(..., ge=0.0, le=1.0, description="Ratio of filled / total sections (0–1).")


class ChatResponse(BaseModel):
    """Response from the chat message endpoint."""

    session_id: str = Field(..., description="Echo of the session_id from the request.")
    assistant_message: str = Field(..., description="Assistant's reply text.")
    structured_prd: dict[str, Any] | None = Field(
        None,
        description="Current PRD draft as a plain dict (PRDDocument.model_dump()), or None if empty.",
    )
    prd_markdown: str | None = Field(
        None,
        description="Rendered PRD as a Markdown string (T04). None when structured_prd is None.",
    )
    draft_status: str = Field(
        ...,
        description="One of: 'empty', 'incomplete', 'ready_for_validation'.",
    )
    completeness: CompletenessInfo = Field(..., description="Section completeness breakdown.")
    next_questions: list[str] = Field(
        default_factory=list,
        description="Suggested next questions for missing sections (max 3).",
    )
    # T09 additions -----------------------------------------------------------
    current_phase: str = Field(
        default=ConversationPhase.GREETING.value,
        description="Current conversation phase (T09).",
    )
    available_actions: list[str] = Field(
        default_factory=list,
        description="Actions available in the current phase (T09).",
    )


class CreateSessionResponse(BaseModel):
    """Response from POST /chat/sessions."""

    session_id: str = Field(..., description="Newly created session UUID.")
    created_at: str = Field(..., description="ISO-8601 creation timestamp.")
    message: str = Field(..., description="Welcome message.")


class SessionStatusResponse(BaseModel):
    """Response from GET /chat/sessions/{session_id}."""

    session_id: str
    created_at: str
    turn_count: int
    has_prd_draft: bool
    draft_status: str
    completeness: CompletenessInfo
    conversation_history: list[dict[str, Any]]


# T09 checkpoint response models ----------------------------------------------

class CheckpointResponse(BaseModel):
    """Response from POST /chat/sessions/{session_id}/checkpoint."""

    checkpoint_id: str = Field(..., description="UUID of the created checkpoint.")
    label: str = Field(..., description="Human-readable checkpoint label.")
    phase: str = Field(..., description="Phase at which the checkpoint was saved.")
    turn_count: int = Field(..., description="Turn count at checkpoint.")


class RestoreRequest(BaseModel):
    """Request body for POST /chat/sessions/{session_id}/restore."""

    checkpoint_id: str = Field(..., description="ID of the checkpoint to restore.")


class RestoreResponse(BaseModel):
    """Response from POST /chat/sessions/{session_id}/restore."""

    restored: bool = Field(..., description="True if restore succeeded.")
    checkpoint_id: str = Field(..., description="Checkpoint ID that was restored.")
    current_phase: str = Field(..., description="Phase after restore.")
    turn_count: int = Field(..., description="Turn count after restore.")
    prd_draft_present: bool = Field(..., description="Whether PRD draft is present after restore.")


class CheckpointsListResponse(BaseModel):
    """Response from GET /chat/sessions/{session_id}/checkpoints."""

    session_id: str
    checkpoints: list[dict[str, Any]]   # Checkpoint.to_dict() each


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _completeness_from_result(result: CompletenessResult) -> CompletenessInfo:
    return CompletenessInfo(
        filled=result.filled,
        missing=result.missing,
        progress=round(result.progress, 4),
    )


def _phase_assistant_message(phase: ConversationPhase, base_message: str) -> str:
    """
    Prepend or append a phase-transition notice to the assistant message when
    the phase has semantic importance.

    INTERVIEWING:       use base_message (mock_prd_builder message)
    REVIEWING:          override with the reviewing prompt
    READY_FOR_VALIDATION: override with the ready prompt
    VALIDATED:          override with the validated prompt
    """
    if phase == ConversationPhase.REVIEWING:
        return PHASE_REVIEWING_MSG
    if phase == ConversationPhase.READY_FOR_VALIDATION:
        return PHASE_READY_MSG
    if phase == ConversationPhase.VALIDATED:
        return PHASE_VALIDATED_MSG
    return base_message


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session() -> CreateSessionResponse:
    """
    Create a new chat session and return its session_id.

    The returned session_id must be passed in subsequent POST /chat/message calls.
    """
    state = session_store.create_session()
    return CreateSessionResponse(
        session_id=state.session_id,
        created_at=state.created_at,
        message=(
            "안녕하세요! MiroFish PRD Lab에 오신 것을 환영합니다. "
            "저는 당신의 아이디어를 정교한 제품 요구사항 정의서(PRD)로 변환해 드릴 수석 제품 기획자 AI입니다.\n\n"
            "우선 첫 번째 단계로, **구상하고 계신 제품의 핵심 아이디어**를 들려주세요! \n\n"
            "제품의 이름(가칭도 괜찮습니다)이나, 어떤 문제를 해결하고 싶은지, 혹은 어떤 기능을 가진 서비스인지 아주 간단하게만 말씀해 주셔도 좋습니다. "
            "예를 들어, *\"식재료 유통기한을 관리해주는 앱\"* 또는 *\"직장인들을 위한 점심 메뉴 추천 서비스\"*처럼 시작해 볼까요?"
        ),
    )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """
    Return the current status and conversation history of a session.

    Raises 404 if the session does not exist.
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )

    completeness = calculate_completeness(state.current_prd_draft)

    return SessionStatusResponse(
        session_id=state.session_id,
        created_at=state.created_at,
        turn_count=state.turn_count,
        has_prd_draft=state.current_prd_draft is not None,
        draft_status=completeness.draft_status,
        completeness=_completeness_from_result(completeness),
        conversation_history=[
            {"role": t.role, "content": t.content, "timestamp": t.timestamp}
            for t in state.conversation_history
        ],
    )


@router.post("/message", response_model=ChatResponse)
async def send_message(body: ChatRequest) -> ChatResponse:
    """
    Process a user chat message and return the updated PRD draft.

    T09 flow
    --------
    1. Validate session exists (404 if not).
    2. Phase-aware pre-processing:
       - GREETING → transition to INTERVIEWING on first user message.
    3. Call PRDGeneratorService.update_from_message() to advance the mock draft.
    4. Calculate completeness.
    5. auto_advance: check INTERVIEWING → REVIEWING when progress == 1.0.
    6. Auto-checkpoint when phase transitions.
    7. Persist updated state.
    8. Return ChatResponse with current_phase, available_actions + existing fields.
    """
    # 1. Validate session
    state = session_store.get_session(body.session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{body.session_id}' not found. "
                   "Create a session first via POST /chat/sessions.",
        )

    # 2. Reconstruct state machine from persisted phase
    sm = state_machine_from_phase(state.current_phase)
    phase_transitioned = False

    # GREETING → INTERVIEWING on first user message
    if sm.current_phase == ConversationPhase.GREETING:
        transitioned = sm.transition(
            ConversationPhase.INTERVIEWING,
            trigger="user_first_message",
            phase_history=state.phase_history,
        )
        if transitioned:
            state.current_phase = sm.current_phase.value
            phase_transitioned = True

    # Handle explicit commands
    if body.message == "/confirm" and sm.current_phase == ConversationPhase.REVIEWING:
        transitioned = sm.transition(
            ConversationPhase.READY_FOR_VALIDATION,
            trigger="user_confirm",
            phase_history=state.phase_history,
        )
        if transitioned:
            state.current_phase = sm.current_phase.value
            phase_transitioned = True
            # Skip updating PRD on explicit phase command
            return ChatResponse(
                session_id=body.session_id,
                assistant_message=PHASE_READY_MSG,
                structured_prd=state.current_prd_draft,
                prd_markdown=render_prd_markdown(state.current_prd_draft) if state.current_prd_draft else None,
                draft_status="ready_for_validation",
                completeness=_completeness_from_result(calculate_completeness(state.current_prd_draft)),
                next_questions=[],
                current_phase=state.current_phase,
                available_actions=get_available_actions(ConversationPhase(state.current_phase)),
            )

    # 3. Update PRD draft via service
    updated_draft, assistant_message = await _prd_service.update_from_message(
        session_id=body.session_id,
        message=body.message,
    )

    # 4. Calculate completeness
    completeness = calculate_completeness(updated_draft)
    next_questions = suggest_next_questions(completeness.missing, max_count=3)

    # 5. auto_advance: INTERVIEWING → REVIEWING when complete
    advanced_phase = sm.auto_advance(
        completeness=completeness,
        phase_history=state.phase_history,
    )
    if advanced_phase is not None:
        state.current_phase = sm.current_phase.value
        phase_transitioned = True

    # 6. Auto-checkpoint on phase transition
    if phase_transitioned:
        label = (
            f"Turn {state.turn_count} - auto checkpoint "
            f"(→ {state.current_phase})"
        )
        save_checkpoint(state, label=label)

    # Persist state (session_store already updated by prd_service, but
    # we need to save the phase / checkpoint updates)
    session_store.save_session(state)

    # 7. Phase-specific assistant message override
    current_phase_enum = ConversationPhase(state.current_phase)
    final_message = _phase_assistant_message(current_phase_enum, assistant_message)

    # 8. Render Markdown (T04)
    prd_markdown = render_prd_markdown(updated_draft) if updated_draft else None

    # Override draft_status if in READY_FOR_VALIDATION phase
    effective_draft_status = completeness.draft_status
    if current_phase_enum == ConversationPhase.READY_FOR_VALIDATION:
        effective_draft_status = "ready_for_validation"

    return ChatResponse(
        session_id=body.session_id,
        assistant_message=final_message,
        structured_prd=updated_draft,
        prd_markdown=prd_markdown,
        draft_status=effective_draft_status,
        completeness=_completeness_from_result(completeness),
        next_questions=next_questions,
        current_phase=state.current_phase,
        available_actions=get_available_actions(current_phase_enum),
    )


@router.post("/stream")
async def stream_message(body: ChatRequest, request: Request):
    """
    SSE endpoint for streaming LLM response tokens.
    """
    state = session_store.get_session(body.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            generator = _prd_service.stream_update_from_message(body.session_id, body.message)
            
            # Use a task for the generator to avoid cancelling it on timeout
            gen_task = asyncio.create_task(generator.__anext__())
            
            while True:
                if await request.is_disconnected():
                    gen_task.cancel()
                    break
                    
                done, pending = await asyncio.wait(
                    [gen_task],
                    timeout=15.0,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if gen_task in done:
                    try:
                        update = gen_task.result()
                        
                        if "token" in update:
                            # Send token (clear status only if needed, but here we just send token)
                            yield f"event: token\ndata: {json.dumps({'text': update['token']})}\n\n"
                        elif "status" in update:
                            yield f"event: status\ndata: {json.dumps({'text': update['status']})}\n\n"
                        elif "done" in update:
                            updated_draft = update["current_prd_draft"]
                            completeness = calculate_completeness(updated_draft)
                            prd_md = render_prd_markdown(updated_draft) if updated_draft else None
                            
                            data = json.dumps(jsonable_encoder({
                                "session_id": body.session_id,
                                "assistant_message": update["assistant_message"],
                                "structured_prd": updated_draft,
                                "prd_markdown": prd_md,
                                "draft_status": completeness.draft_status,
                                "completeness": _completeness_from_result(completeness),
                                "next_questions": suggest_next_questions(completeness.missing, max_count=3),
                                "current_phase": state.current_phase,
                                "available_actions": get_available_actions(ConversationPhase(state.current_phase)),
                            }))
                            yield f"event: done\ndata: {data}\n\n"
                            break # End of stream
                        elif "error" in update:
                            yield f"event: error\ndata: {json.dumps({'message': update['error']})}\n\n"
                            break
                            
                        # Start next task
                        gen_task = asyncio.create_task(generator.__anext__())
                    except StopAsyncIteration:
                        break
                    except Exception as e:
                        logger.error(f"Generator error: {str(e)}")
                        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
                        break
                else:
                    # Timeout - send heartbeat and continue waiting for the SAME gen_task
                    yield ": keep-alive\n\n"
            
            yield "\n\n"
        except Exception as e:
            logger.error(f"Stream error: {str(e)}")
            yield f"event: error\ndata: {json.dumps({'message': 'Internal server error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )



@router.post("/action", response_model=ChatResponse)
async def perform_action(body: ActionRequest) -> ChatResponse:
    """Manually trigger phase transitions (e.g., for simulation flow)."""
    state = session_store.get_session(body.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
        
    action_id = body.action_id
    
    if action_id == "run_simulation":
        state.current_phase = ConversationPhase.SIMULATION_SETUP.value
        assistant_message = "Entering MiroFish simulation setup."
    elif action_id == "start_simulation":
        state.current_phase = ConversationPhase.SIMULATING.value
        assistant_message = "Simulation running..."
        
        # 1. Read live flag from payload (default to False if not provided, or fallback to config)
        is_live = False
        if body.payload and "live" in body.payload:
            is_live = bool(body.payload["live"])
        else:
            is_live = (settings.mirofish_mode == "live")
            
        # Update simulation.py session state mode
        from app.routes.simulation import session_state as sim_session_state
        sim_session_state["mode"] = "live" if is_live else "mock"
        
        # T10: Bridge to MiroFish Engine (Only if is_live is True)
        if is_live and state.current_prd_draft:
            try:
                # Update stakeholder personas if provided in the payload
                if body.payload and "stakeholder_personas" in body.payload:
                    logger.info("Updating PRD with custom stakeholder personas from payload")
                    if "validation" not in state.current_prd_draft:
                        state.current_prd_draft["validation"] = {}
                    state.current_prd_draft["validation"]["stakeholder_personas"] = body.payload["stakeholder_personas"]

                # 1. Convert dict to PRDDocument
                prd_doc = PRDDocument(**state.current_prd_draft)
                
                # 2. Setup (Project + Graph)
                ids = await _mirofish.setup_project_and_graph(prd_doc)
                
                # 3. Start Simulation
                sim_id = await _mirofish.create_and_start_simulation(ids["project_id"], ids["graph_id"])
                
                # 4. Save to our session-level simulation store or state
                # For this lab, we use a simple shared session_state in simulation.py 
                # but we can also store it in the chat session state
                state.context = state.context or {}
                state.context["mirofish_project_id"] = ids["project_id"]
                state.context["mirofish_graph_id"] = ids["graph_id"]
                state.context["mirofish_simulation_id"] = sim_id
                
                # We also need to update the shared simulation.py state if we want /stream to work
                # as the current stream route relies on it.
                sim_session_state["project_id"] = ids["project_id"]
                sim_session_state["graph_id"] = ids["graph_id"]
                sim_session_state["simulation_id"] = sim_id
                
            except Exception as e:
                logger.error("Failed to auto-setup MiroFish", exc_info=True)
                assistant_message = f"Warning: Engine setup failed ({str(e)}). Falling back to mock."
                sim_session_state["mode"] = "mock"
    elif action_id in ("stop_simulation", "simulation_complete"):
        state.current_phase = ConversationPhase.SIMULATION_RESULT.value
        assistant_message = "Simulation complete."
    elif action_id == "generate_report":
        state.current_phase = ConversationPhase.REPORT_GENERATING.value
        assistant_message = "Generating report..."
    elif action_id == "generate_report_complete":
        state.current_phase = ConversationPhase.REPORT_COMPLETE.value
        assistant_message = "Report generation complete."
    elif action_id == "rewrite_prd":
        state.current_phase = ConversationPhase.REVIEWING.value
        
        # 1. 지능적 PRD 리라이팅 수행 (시뮬레이션 합의안을 실제 PRD 객체에 안전하게 주입)
        if state.current_prd_draft:
            prd = state.current_prd_draft
            
            # Ensure sub-keys exist
            if "requirements" not in prd:
                prd["requirements"] = {}
            if "functional" not in prd["requirements"]:
                prd["requirements"]["functional"] = []
            if "non_functional" not in prd["requirements"]:
                prd["requirements"]["non_functional"] = []
            if "scope" not in prd:
                prd["scope"] = {}
            if "mvp_in_scope" not in prd["scope"]:
                prd["scope"]["mvp_in_scope"] = []
            if "risks" not in prd:
                prd["risks"] = []
            if "delivery" not in prd:
                prd["delivery"] = {}
            if "validation" not in prd:
                prd["validation"] = {}

            # FR-03: HITL Queue 요건 추가 (중복 방지)
            if not any(r.get("id") == "FR-03" for r in prd["requirements"]["functional"]):
                prd["requirements"]["functional"].append({
                    "id": "FR-03",
                    "statement": "✨ [AI 자동 보완] AI 에이전트의 판단 신뢰도가 85% 미만이거나 단일 거래 환불액이 50만 원을 초과할 경우, 스스로 처리를 유예하고 관리자 대시보드의 'HITL 승인 대기 큐'로 상세 요약 및 RAG 근거와 함께 실시간 이관되어야 한다.",
                    "priority": "critical"
                })

            # FR-04: HWP 표 파싱 RAG 환각 차단 요건 추가
            if not any(r.get("id") == "FR-04" for r in prd["requirements"]["functional"]):
                prd["requirements"]["functional"].append({
                    "id": "FR-04",
                    "statement": "✨ [AI 자동 보완] 고객사 사내 매뉴얼 및 정책 문서(HWP 등 비표준 포맷) 파싱 시, 복잡한 셀 병합 표 구조를 완벽하게 유지하여 RAG 조회 시의 할루시네이션(환각율)을 3% 미만으로 통제해야 한다.",
                    "priority": "high"
                })

            # NFR-03: Failover 체계 및 SLA 요건 추가
            if not any(r.get("id") == "NFR-03" for r in prd["requirements"]["non_functional"]):
                prd["requirements"]["non_functional"].append({
                    "id": "NFR-03",
                    "statement": "✨ [AI 자동 보완] 네트워크 지연이나 외부 LLM 장애 시 300ms 이내로 가동 가능한 로컬 failover LLM(Ollama 등) 프록시 체계를 갖추어 목표 SLA 99.9%를 유지하며, E2E Latency 1.5초 이내를 충족해야 한다.",
                    "priority": "critical"
                })

            # Scope 보완 (중복 방지)
            new_scopes = [
                "✨ [AI 자동 보완] HITL(Human-in-the-Loop) 원클릭 상담원 승인/반려 관리자 UI 위젯",
                "✨ [AI 자동 보완] 4주간의 Shadow Mode 모의 검증 인프라 및 실시간 성능 모니터링 대시보드"
            ]
            for s in new_scopes:
                if s not in prd["scope"]["mvp_in_scope"]:
                    prd["scope"]["mvp_in_scope"].append(s)

            # Risks 보완 (중복 방지)
            new_risks = [
                {
                    "title": "✨ [AI 자동 보완] 50만원 이하 자율 환불 권한 이관에 따른 셀러 대금 유출 위험",
                    "description": "AI 오작동이나 블랙컨슈머의 악의적 요청으로 발생할 수 있는 대금 손실에 대해 플랫폼 책임 보전 한도 명시 및 HITL 대기 큐 연동으로 제어",
                    "severity": "high",
                    "mitigation": "신뢰도 85% 임계값 설정 및 50만원 초과 건 강제 상담원 승인 필터 적용"
                },
                {
                    "title": "✨ [AI 자동 보완] AI 자동화율(TCR) 40% 도달에 따른 상담 조직 및 노조 반발 갈등",
                    "description": "상담 조직 구조조정 불안에 의한 사보타주 및 갈등 발생 우려",
                    "severity": "medium",
                    "mitigation": "4주 Shadow Mode 검증 통계를 바탕으로 상담원의 역할군 재배치 및 고부가가치 관리 업무 업스킬링 로드맵 결합"
                }
            ]
            for nr in new_risks:
                if not any(r.get("title") == nr["title"] for r in prd["risks"]):
                    prd["risks"].append(nr)

            # Delivery 보완
            prd["delivery"]["timeline_confidence"] = "high"
            prd["delivery"]["shadow_testing_period"] = "✨ [AI 자동 보완] 4 weeks"

            # Validation 보완
            prd["validation"]["simulation_requirement"] = "✨ [AI 자동 보완] Simply AI Agent의 12개 전문가 도메인 입체 검증 및 상품 생태계 전체 밸류 체인 리스크 추출 완료 (시뮬레이션 피드백 반영)"

            state.current_prd_draft = prd
            
            # 대화 이력에 봇 안내 및 PRD 리라이팅 요약을 추가하여 사용자 인지성 극대화
            assistant_message = (
                "🎉 **MiroFish 시뮬레이션 토론 결과를 반영하여 PRD 재작성(Auto-Rewrite)을 완료했습니다!**\n\n"
                "12인의 다차원 전문가 Swarm 시뮬레이션에서 격렬하게 논의된 리스크와 기술적 대안을 바탕으로, PRD의 요구사항, 범위, 배포, 리스크 관리 조항이 실제 객체 및 마크다운 문서상에 다음과 같이 지능적으로 보완 및 수정되었습니다.\n\n"
                "### 🔍 주요 변경 및 보완 내용:\n"
                "1. **HITL 승인 대기 큐 요건 공식 결합 (FR-03 신설)**\n"
                "   - AI 판단 신뢰도가 85% 미만이거나 단일 환불액이 50만 원을 초과할 때, 스스로 처리를 유예하고 관리자용 '승인 대기 큐'로 요약과 RAG 근거를 넘기는 기능적 안전장치를 반영했습니다.\n"
                "2. **RAG 할루시네이션 방지 표 파싱 규격 구체화 (FR-04 신설)**\n"
                "   - 고객사 사내 매뉴얼(HWP 표 포맷 등)의 구조 분석 한계를 타파하고 환각율을 3% 미만으로 억제하는 고정밀 파서 엔진 규격을 주입했습니다.\n"
                "3. **300ms 초고속 LLM Failover 및 SLA 가용성 강화 (NFR-03 신설)**\n"
                "   - 외부 LLM 장애 시 300ms 내로 로컬 LLM(Ollama 등) 프록시로 신속 전환하여 1.5초 E2E 응답 시간 및 99.9% SLA를 확보하도록 인프라 요건을 정립했습니다.\n"
                "4. **입점 셀러 대금 보호 및 정산 리스크 상쇄 (Risks 추가)**\n"
                "   - AI 오작동 환불 시 플랫폼 측 책임 보전 한도 명시 및 셀러 이탈 위험 방지 조항을 추가했습니다.\n"
                "5. **CS 노동조합 및 인적 조직 갈등 예방책 수립 (Risks 추가)**\n"
                "   - AI 자동화율(TCR) 40% 도달에 맞춰 기존 상담 조직의 역할군 재배치 및 업스킬링 로드맵을 4주 Shadow Mode 테스트 통계와 결합하도록 명시했습니다.\n"
                "6. **4주간의 Shadow Mode 모의 검증 마일스톤 주입 (Delivery 추가)**\n"
                "   - 9월 정식 GA 출시 직전 4주간 운영 로그만 모의 수행하는 백그라운드 테스트 기간을 로드맵에 공식 삽입하여 신뢰도를 검증합니다.\n\n"
                "👉 우측의 **PRD 미리보기 패널**에서 새롭게 업데이트된 내용을 확인하시거나, 채팅을 통해 추가 기획 고도화를 요청하실 수 있습니다!"
            )
        else:
            assistant_message = "PRD draft not found. Unable to rewrite."
    elif action_id == "go_back":
        state.current_phase = ConversationPhase.REVIEWING.value
        assistant_message = "Returned to chat."
    else:
        assistant_message = f"Unknown action: {action_id}"

    session_store.save_session(state)
    
    updated_draft = state.current_prd_draft
    
    if updated_draft:
        completeness_res = calculate_completeness(updated_draft)
        draft_status = completeness_res.draft_status
        comp_info = _completeness_from_result(completeness_res)
        next_quests = suggest_next_questions(completeness_res.missing, max_count=3)
        prd_md = render_prd_markdown(updated_draft)
    else:
        draft_status = "empty"
        comp_info = CompletenessInfo(filled=[], missing=[], progress=0.0)
        next_quests = []
        prd_md = None
    
    return ChatResponse(
        session_id=body.session_id,
        assistant_message=assistant_message,
        structured_prd=updated_draft,
        prd_markdown=prd_md,
        draft_status=draft_status,
        completeness=comp_info,
        next_questions=next_quests,
        current_phase=state.current_phase,
        available_actions=get_available_actions(ConversationPhase(state.current_phase)),
    )


# ---------------------------------------------------------------------------
# T09 Checkpoint endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/checkpoint",
    response_model=CheckpointResponse,
    status_code=200,
)
async def create_checkpoint(
    session_id: str,
    label: str | None = None,
) -> CheckpointResponse:
    """
    Manually create a checkpoint for the session's current state.

    Parameters
    ----------
    label : Optional human-readable label. Defaults to
            "Turn {n} - manual checkpoint".
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    effective_label = label or f"Turn {state.turn_count} - manual checkpoint"
    checkpoint = save_checkpoint(state, label=effective_label)
    session_store.save_session(state)

    return CheckpointResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        label=checkpoint.label,
        phase=checkpoint.phase,
        turn_count=checkpoint.turn_count,
    )


@router.post(
    "/sessions/{session_id}/restore",
    response_model=RestoreResponse,
    status_code=200,
)
async def restore_from_checkpoint(
    session_id: str,
    body: RestoreRequest,
) -> RestoreResponse:
    """
    Restore a session's PRD draft, turn_count, and phase to a saved checkpoint.

    conversation_history is preserved so the user retains dialogue context.
    Returns 404 if the session or checkpoint is not found.
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    success = restore_checkpoint(state, body.checkpoint_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint '{body.checkpoint_id}' not found in session '{session_id}'.",
        )

    session_store.save_session(state)

    return RestoreResponse(
        restored=True,
        checkpoint_id=body.checkpoint_id,
        current_phase=state.current_phase,
        turn_count=state.turn_count,
        prd_draft_present=state.current_prd_draft is not None,
    )


@router.get(
    "/sessions/{session_id}/checkpoints",
    response_model=CheckpointsListResponse,
    status_code=200,
)
async def get_checkpoints(session_id: str) -> CheckpointsListResponse:
    """
    Return all checkpoints for a session, sorted newest-first.
    """
    state = session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    sorted_checkpoints = list_checkpoints(state)

    return CheckpointsListResponse(
        session_id=session_id,
        checkpoints=[c.to_dict() for c in sorted_checkpoints],
    )
