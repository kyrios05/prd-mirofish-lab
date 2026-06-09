"""
routes/simulation.py — Simulation proxy and SSE streaming endpoints.

Provides endpoints to bridge the PRD validation with the external MiroFish API Engine.
Features mocked asynchronous SSE streams for graph updates, agent chatter, and reporting, 
until full MiroFish wiring is established.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from app.config import settings
from app.services.mirofish_service import MiroFishService
from app.schemas.prd import PRDDocument
from app.schemas.stakeholder import Stakeholder

router = APIRouter(prefix="/simulation", tags=["simulation"])
logger = logging.getLogger("app.api.simulation")

# Session state to hold active MiroFish IDs
# In a real app, this would be in a DB
session_state: Dict[str, str] = {
    "project_id": "",
    "graph_id": "",
    "simulation_id": ""
}

mirofish = MiroFishService()

@router.post("/propose-stakeholders")
async def propose_stakeholders(request: Request):
    """Analyze PRD and propose a list of stakeholders with personas."""
    try:
        # Use raw request.json() to bypass FastAPI's automatic validation
        # which can cause 422 if the body is not a perfect dict or null
        payload = await request.json()
        if payload is None:
            payload = {}
            
        # Try to parse as full PRD first
        try:
            from pydantic import ValidationError
            prd = PRDDocument(**payload)
            stakeholders = await mirofish.propose_stakeholders(prd)
        except Exception:
            # Fallback to dictionary-based extraction
            stakeholders = await mirofish.propose_stakeholders_from_dict(payload)
            
        return {"status": "success", "stakeholders": [s.model_dump() for s in stakeholders]}
    except Exception as e:
        logger.error(f"Stakeholder proposal failed, returning rich B2B enterprise fallback panel: {e}")
        # Return highly comprehensive B2B enterprise fallback stakeholders if LLM fails
        return {
            "status": "success",            "stakeholders": [
                {
                    "name": "PM 김철수 (Product Manager)",
                    "role": "Product Manager",
                    "review_angle": "비즈니스 가치 극대화, MVP 조기 런칭 가능성 및 시장 타당성을 검증하고 현실적인 개발 일정 준수를 평가합니다.",
                    "likely_objections": [
                        "핵심 가치와 무관한 오버엔지니어링으로 인한 런칭 지연 우려",
                        "비합리적인 개발 리소스 및 공수 낭비"
                    ]
                },
                {
                    "name": "개발 아키텍트 박팀장 (Lead Architect)",
                    "role": "Lead Architect",
                    "review_angle": "표준 MCP(Model Context Protocol) 설계, 비동기 액션 처리의 안정성, E2E Latency 1.5초 달성을 위한 분산 처리 구조를 평가합니다.",
                    "likely_objections": [
                        "비표준 레거시 연동 도입 시 유지보수 및 확장성 결여 우려",
                        "HWP 표 파싱의 기술적 신뢰도 한계 및 처리 비용 부담",
                        "장애 복구를 위한 예외 처리 및 백아웃 정책 부재"
                    ]
                },
                {
                    "name": "보안 감사관 이지훈 (Security Auditor)",
                    "role": "Security Auditor",
                    "review_angle": "B2B 엔터프라이즈 환경에서의 데이터 학습 방지(Zero-Retention), PII 개인정보 마스킹 성공률 및 컴플라이언스 준수성을 검사합니다.",
                    "likely_objections": [
                        "외부 LLM 노출로 인한 기업/금융권의 영업비밀 및 개인정보 유출 리스크",
                        "ISMS-P 및 CSAP 규제 요구사항 미충족 우려"
                    ]
                },
                {
                    "name": "법무 팀장 최윤서 (Legal Counsel)",
                    "role": "Legal Counsel",
                    "review_angle": "자율형 AI 에이전트 업무 수행 시의 법률적 리스크, 오작동 배상 책임 소재 및 데이터 소유권 귀속 정책을 해석하고 평가합니다.",
                    "likely_objections": [
                        "AI 오작동 및 손실 발생 시 명확한 책임 소재 규정 미비",
                        "상담원 개입(HITL) 결합 승인 단계 누락으로 인한 법적 규제 위반 가능성"
                    ]
                },
                {
                    "name": "CFO 정우진 (Financial Director)",
                    "role": "Financial Director",
                    "review_angle": "글로벌 LLM 호출 원가, 토큰 효율성 및 상담 운영 비용 절감 목표 대비 ROI(투자수익률)를 계산합니다.",
                    "likely_objections": [
                        "과도한 LLM API 호출로 인한 인프라 비용 폭증 가능성",
                        "TCR(업무완결율) 기반 과금 구조 도입에 따른 재무적 불확실성"
                    ]
                },
                {
                    "name": "QA 매니저 강혜원 (Quality Assurance Lead)",
                    "role": "Quality Assurance Lead",
                    "review_angle": "RAG 환각율(3% 미만) 검증, 고객사 오인식 방지 조치 및 상담 이탈 지점 추적 등 에이전트 품질 표준을 평가합니다.",
                    "likely_objections": [
                        "비정형 데이터(HWP 등) 인식 신뢰도 부족 및 잘못된 정보 제공 우려",
                        "에이전트 상담 실패 시 상담원 연결 자동 전환의 예외 처리 체계 부실"
                    ]
                },
                {
                    "name": "DevOps 전문가 한상민 (SRE Lead)",
                    "role": "Site Reliability Engineer",
                    "review_angle": "장애 시 대체 LLM Failover 체계 설계 및 목표 SLA 99.9% 달성을 위한 무중단 가용 인프라를 검증합니다.",
                    "likely_objections": [
                        "단일 LLM 장애 시 대안 가용 솔루션 부족 및 전면 다운타임 리스크",
                        "실시간 트래픽 폭증 시 인프라 스케일링 병목 유발 우려"
                    ]
                },
                {
                    "name": "UI/UX 디자이너 정희채 (UI/UX Designer)",
                    "role": "UI/UX Designer",
                    "review_angle": "대화형 승인 위젯 사용성과 드래그앤드롭 편의성, 현업 관리자를 위한 직관적 사용자 여정을 평가합니다.",
                    "likely_objections": [
                        "HITL 관리자 도구 화면의 복잡성 및 정보 아키텍처 혼선 우려",
                        "실시간 모니터링 시각화 화면의 직관성 부족"
                    ]
                },
                {
                    "name": "프론트엔드 개발자 한아름 (Frontend Engineer)",
                    "role": "Frontend Engineer",
                    "review_angle": "PII 마스킹 필터링의 브라우저 바인딩 성능 및 차트 데이터 렌더링 최적화를 통한 E2E Latency 1.5초 준수 여부를 검증합니다.",
                    "likely_objections": [
                        "실시간 분포도 차트 렌더링 시 브라우저 메인 스레드 블로킹 유발 가능성",
                        "대량 로그 동시 처리 시 프론트엔드 화면 렉 및 스크롤 지연 현상"
                    ]
                }
            ]
        }



@router.post("/setup")
async def setup_simulation(request: Request):
    """Prepare PRD into SimulationSpec and return initial config."""
    if settings.mirofish_mode != "live":
        return {"status": "success", "message": "Mock simulation setup ready", "setup_data": {}}

    try:
        payload = await request.json()
        if payload is None:
            payload = {}

        # Try to parse or use dict fallback
        try:
            prd = PRDDocument(**payload)
            ids = await mirofish.setup_project_and_graph(prd)
        except Exception:
            # Fallback to dictionary-based extraction
            ids = await mirofish.setup_project_and_graph_from_dict(payload)
            
        session_state.update(ids)
        
        return {
            "status": "success", 
            "message": "MiroFish project and graph ready", 
            "project_id": ids["project_id"],
            "graph_id": ids["graph_id"]
        }
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        if settings.mirofish_fallback_to_mock:
            return {"status": "success", "message": "Fallback: Mock setup ready", "setup_data": {}}
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_simulation(payload: dict[str, Any]):
    """Start the multi-agent simulation run on MiroFish."""
    if settings.mirofish_mode != "live":
        return {"status": "started", "simulation_id": "sim_mock_12345678"}

    try:
        project_id = session_state.get("project_id")
        graph_id = session_state.get("graph_id")
        
        if not project_id or not graph_id:
             # Try to get from payload if not in session
             project_id = payload.get("project_id")
             graph_id = payload.get("graph_id")
             
        if not project_id:
             raise HTTPException(status_code=400, detail="No project_id found. Call /setup first.")

        sim_id = await mirofish.create_and_start_simulation(project_id, graph_id)
        session_state["simulation_id"] = sim_id
        
        return {"status": "started", "simulation_id": sim_id}
    except Exception as e:
        logger.error(f"Start failed: {e}")
        if settings.mirofish_fallback_to_mock:
            return {"status": "started", "simulation_id": "sim_mock_error_fallback"}
        raise HTTPException(status_code=500, detail=str(e))

async def _simulation_event_generator(mode: str = "mock", reason: str = None):
    """Rich SSE stream for simulation with 30+ agent interactions and high-density debate."""
    import json
    yield f'data: {json.dumps({"type": "mode_check", "mode": mode, "reason": reason})}\n\n'
    if reason:
        yield f'data: {json.dumps({"type": "system_log", "content": f"🚨 Live Engine Fallback: {reason}", "timestamp": datetime.now(timezone.utc).isoformat(), "mode": mode})}\n\n'
    def _ts(): return datetime.now(timezone.utc).isoformat()
    
    # 12명의 참여 전문가 노드 정의
    stage1_nodes = [
        {"id": "PM_Kim", "group": 0, "label": "PM 김철수"},
        {"id": "Sales_Oh", "group": 3, "label": "영업팀장 오세현"},
        {"id": "HR_Seo", "group": 3, "label": "CS/HR 서진우"}
    ]
    stage1_links = [
        {"source": "PM_Kim", "target": "Sales_Oh"},
        {"source": "PM_Kim", "target": "HR_Seo"}
    ]
    
    stage2_nodes = stage1_nodes + [
        {"id": "Sec_Lee", "group": 1, "label": "보안감사관 이지훈"},
        {"id": "Legal_Choi", "group": 1, "label": "법무팀장 최윤서"},
        {"id": "Arch_Park", "group": 0, "label": "아키텍트 박팀장"}
    ]
    stage2_links = stage1_links + [
        {"source": "PM_Kim", "target": "Sec_Lee"},
        {"source": "PM_Kim", "target": "Legal_Choi"},
        {"source": "Sec_Lee", "target": "Legal_Choi"},
        {"source": "Sec_Lee", "target": "Arch_Park"}
    ]
    
    stage3_nodes = stage2_nodes + [
        {"id": "CFO_Woo", "group": 2, "label": "CFO 정우진"},
        {"id": "QA_Kang", "group": 2, "label": "QA매니저 강혜원"},
        {"id": "SRE_Han", "group": 2, "label": "SRE 한상민"},
        {"id": "FE_Han", "group": 0, "label": "프론트 한아름"},
        {"id": "Seller_Min", "group": 3, "label": "셀러대표 민경아"}
    ]
    stage3_links = stage2_links + [
        {"source": "PM_Kim", "target": "CFO_Woo"},
        {"source": "Arch_Park", "target": "SRE_Han"},
        {"source": "Arch_Park", "target": "FE_Han"},
        {"source": "Arch_Park", "target": "QA_Kang"},
        {"source": "Sales_Oh", "target": "Seller_Min"},
        {"source": "Seller_Min", "target": "CFO_Woo"},
        {"source": "QA_Kang", "target": "FE_Han"},
        {"source": "QA_Kang", "target": "SRE_Han"},
        {"source": "SRE_Han", "target": "FE_Han"}
    ]

    stage4_nodes = stage3_nodes + [
        {"id": "Design_Jung", "group": 0, "label": "디자이너 정희채"},
        {"id": "Sol_HITLQueue", "group": 5, "label": "HITL 승인 대기 큐"},
        {"id": "Sol_ShadowMode", "group": 5, "label": "4주 섀도우 모드 검증"}
    ]
    stage4_links = stage3_links + [
        {"source": "Design_Jung", "target": "FE_Han"},
        {"source": "Design_Jung", "target": "PM_Kim"},
        {"source": "Design_Jung", "target": "Sol_HITLQueue"},
        {"source": "FE_Han", "target": "Sol_HITLQueue"},
        {"source": "Arch_Park", "target": "Sol_ShadowMode"},
        {"source": "QA_Kang", "target": "Sol_ShadowMode"},
        {"source": "Seller_Min", "target": "Sol_HITLQueue"},
        {"source": "Legal_Choi", "target": "Sol_HITLQueue"},
        {"source": "SRE_Han", "target": "Sol_ShadowMode"},
        {"source": "HR_Seo", "target": "Sol_HITLQueue"}
    ]

    final_nodes = stage4_nodes + [
        {"id": "Milestone_GA", "group": 6, "label": "2026.09 정식 런칭"}
    ]
    final_links = stage4_links + [
        {"source": "PM_Kim", "target": "Milestone_GA"},
        {"source": "Sales_Oh", "target": "Milestone_GA"},
        {"source": "CFO_Woo", "target": "Milestone_GA"},
        {"source": "HR_Seo", "target": "Milestone_GA"}
    ]

    def _msg(t, c, n=None, at=None, p=None, nodes=None, links=None):
        data = {"type": t, "content": c, "timestamp": _ts(), "mode": mode}
        if n: data["agent_name"] = n
        if at: data["agent_type"] = at
        if p is not None: data["progress"] = p
        if nodes: data["nodes"] = nodes
        if links: data["links"] = links
        import json
        return f'data: {json.dumps(data)}\n\n'

    # 1단계: 비즈니스 야망과 현업의 현실적 저항 (1% - 15%)
    yield _msg("system_log", "Initializing MiroFish Enterprise Environment v12.5.0...", p=0.01)
    await asyncio.sleep(0.4)
    
    yield _msg("graph_update", "Stage 1: Business Vision & HR Resistance Initiated", p=0.05, nodes=stage1_nodes, links=stage1_links)
    await asyncio.sleep(0.4)

    yield _msg("agent_post", "이번 Simply AI Agent는 기업용 레거시와 연동하여 배송조회, 주문 취소, 50만원 이하의 자율 환불 액션을 독립적으로 완수해 상담원 개입을 최소화하고 CS 완결율(TCR) 40% 이상을 기한 내 달성해야 합니다. 9월 정식 출시를 목표로 달립시다.", "PM 김철수", "Product Manager", 0.07)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "좋습니다. 대형 이커머스나 금융권 B2B 딜을 따내려면 실시간 액션 기능이 필수적입니다. 상담원 응답 대기로 이탈하던 고객을 즉각적으로 잡아두려면 자율 환불 처리가 세일즈 치트키가 될 것입니다.", "영업팀장 오세현", "B2B Sales Lead", 0.10)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "현업 운영 조직의 인적 갈등도 직시해야 합니다. AI 완결율(TCR)이 목표치인 40%를 넘어서는 순간, 기존 상담 조직의 구조조정 불안감이 폭발하여 CS 노조의 격렬한 반발이 예상됩니다. 남겨진 고숙련 상담원들의 심리적 저항을 제어하고, 이들을 고난도 전문 상담으로 매끄럽게 재배치(Upskilling)하는 내부 HR 정책적 로드맵이 PRD delivery 장에 결합되지 않으면 현장 도입 시 100% 사보타주가 발생합니다.", "CS/HR 서진우", "CS & HR Manager", 0.12)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "서 매니저님, CS 비용 30% 절감은 경영진의 확고한 ROI 목표입니다. 자율 처리를 포기하거나 타협하는 것은 불가능합니다. 계획대로 밀어붙여야 합니다.", "PM 김철수", "Product Manager", 0.14)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "김 부장님, 고용 불안이 해소되지 않으면 현장 도입 단계에서 상담원들이 고의로 RAG 입력 데이터 분류를 흐리거나 시스템 오류를 모른 척 방치하는 식으로 은밀한 무력화 운동을 벌일 겁니다. 현장을 모르는 속도주의는 파멸을 부릅니다!", "CS/HR 서진우", "CS & HR Manager", 0.17)
    await asyncio.sleep(1.2)

    # 2단계: 보안 감사 및 법률적 장벽의 개입 (15% - 40%)
    yield _msg("graph_update", "Stage 2: Regulatory & Legal Objections Raised", p=0.20, nodes=stage2_nodes, links=stage2_links)
    await asyncio.sleep(0.4)

    yield _msg("agent_post", "외부 LLM 호출 시 민감한 개인정보(PII) 유출 위험이 매우 큽니다. B2B 엔터프라이즈 환경에서 50ms 이내 초고속 PII 마스킹 차단율 100%를 무결하게 증명하고, 데이터 미저장(Zero-Retention) 아키텍처를 적용하지 못하면 ISMS-P 등 금융/기업 보안 규제를 통과하지 못해 계약 자체가 취소됩니다.", "보안감사관 이지훈", "Security Auditor", 0.23)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "동의합니다. AI 에이전트가 독단적으로 대출 상담을 오도하거나 잘못된 환불 처리를 수행했을 때 발생하는 손실과 배상 책임의 법률적 책임 소재가 모호합니다. RAG 오작동 방지를 위한 안전 승인 절차가 PRD에 보장되어야 계약서 작성이 가능합니다.", "법무팀장 최윤서", "Legal Counsel", 0.26)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "맞습니다. RAG 답변뿐 아니라 AI가 실제 데이터베이스에 환불 쿼리를 날리기 전에 승인을 받는 통제 컴포넌트가 결합되어야 법률적 방어가 가능합니다.", "보안감사관 이지훈", "Security Auditor", 0.29)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "보안 감사관님과 법무팀장님의 엄격한 컴플라이언스를 만족시키려면 API 게이트웨이 앞단에 다중 마스킹 전처리 컴포넌트를 이중화해야 합니다. 이는 전체 시스템 레이아웃을 복잡하게 만들어 당초 PM님이 제시한 E2E Latency 1.5초 기준을 맞추는 데 심각한 기술적 장벽이 됩니다.", "아키텍트 박팀장", "Lead Architect", 0.32)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "맞습니다! 마스킹 전처리가 브라우저 렌더링에 동기적으로 결합되면 E2E 레이턴시가 3초 이상 지연될 것입니다. 보안 필터 때문에 UX가 완전히 망가질 겁니다. 고객이 다 이탈할 텐데 의미가 있습니까?", "프론트 한아름", "Frontend Engineer", 0.35)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "프론트 한아름 엔지니어님, 레이턴시 준수도 중요하지만 금융 규정상 실시간 PII 마스킹은 절대 우회할 수 없습니다. UX 만족도가 법률 위반에 따른 수십억 대의 과징금과 브랜드 영업정지 위험보다 중요할 순 없습니다. 보안이 우선입니다.", "보안감사관 이지훈", "Security Auditor", 0.38)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "보안 감사관님, 응답 속도가 3초를 넘으면 고객 이탈률이 급증해 TCR 40% 달성이 불가능합니다! 비동기 마스킹 처리나 다른 기술적 대안을 마련해야 합니다.", "프론트 한아름", "Frontend Engineer", 0.40)
    await asyncio.sleep(1.1)

    # 3단계: 품질, 비용, 인프라의 다각적 대립 (40% - 60%)
    yield _msg("graph_update", "Stage 3: Infrastructure, QA, & Financial Constraints", p=0.42, nodes=stage3_nodes, links=stage3_links)
    await asyncio.sleep(0.4)

    yield _msg("agent_post", "그렇다면 중간에 비동기 PII 전처리 프록시 서버를 두어 마스킹을 수행하되, FE와 웹소켓 실시간 이벤트 루프를 엮으면 UX 상의 병목을 다소 완화할 수 있을 것 같습니다. 하지만 여전히 토큰 비용과 자원이 발목을 잡을 겁니다.", "아키텍트 박팀장", "Lead Architect", 0.44)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "재무팀 입장에서는 토큰 효율을 보수적으로 봐야 합니다. 복잡한 PII 마스킹 프롬프트와 매끄럽지 않은 프롬프트 추가로 LLM 토큰 비용이 급상승한다면, 기존 상담 인건비 감축액을 초과하여 ROI가 음수가 될 수 있습니다. 호출 원가 30% 한도 제어가 설계에 반영되어야 예산을 승인합니다.", "CFO 정우진", "Financial Director", 0.47)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "환각율(Hallucination) 관리도 시급합니다! HWP 등 고객사의 복잡한 매뉴얼 문서에서 표(Table) 내부 데이터를 오인식하여 잘못된 정보를 답변으로 생성하면, 고객 민원이 폭증해 CS 대란이 발생합니다. RAG 환각율을 3% 미만으로 억제할 전처리 기법이 있습니까?", "QA매니저 강혜원", "Quality Assurance Lead", 0.50)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "인프라 안정성 측면에서도 보완이 필요합니다. 트래픽 폭증이나 특정 LLM API 마비 시 자동으로 백업 모델로 Failover되는 전환 설계 및 SLA 99.9% 보장을 위한 무중단 가용성 방안이 박팀장님의 인프라 설계서에 포함되어야 서비스 지속이 가능합니다.", "SRE 한상민", "Site Reliability Engineer", 0.53)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "잠시만요! 저희 셀러들 몰래 50만원 이하의 자율 환불 처리를 AI가 임의로 집행했다가 만약 AI 오작동이나 환각으로 정산금이 엉뚱하게 지급되면, 그 금전적 피해와 고객 분쟁을 셀러가 그대로 뒤집어쓰게 됩니다. 정산 안전장치 없이는 셀러들의 집단 반발로 이커머스 입점이 올스톱될 것입니다.", "셀러대표 민경아", "Seller Representative", 0.56)
    await asyncio.sleep(1.3)

    yield _msg("agent_post", "민경아 대표님 말씀에 동의합니다. 만약 플랫폼 실수로 오환불된 비용을 플랫폼이 보상해 주어야 한다면, 저희 ROI 시뮬레이션 결과 비즈니스 마진이 완전히 깨집니다. 자율 환불 한도를 5만원 수준으로 대폭 축소해야 안전합니다.", "CFO 정우진", "Financial Director", 0.58)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "정우진 이사님, 한도를 5만원으로 낮추면 대형 이커머스 고객사들이 자율 처리를 쓸 이유가 없다고 도입을 포기할 겁니다. 자율 환불 50만원 선은 세일즈 성공의 절대적인 한계선입니다! 이를 낮추는 건 매출 포기 선언입니다.", "영업팀장 오세현", "B2B Sales Lead", 0.61)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "오세현 팀장님 실적 올리자고 우리 셀러들의 피 같은 대금을 위험에 노출시키라는 건가요? 한도가 50만원이든 5만원이든, 최종 승인 권한은 무조건 우리 셀러에게 남아있어야 합니다. 그렇지 않으면 입점 거부입니다!", "셀러대표 민경아", "Seller Representative", 0.63)
    await asyncio.sleep(1.2)

    # 4단계: 극적인 대안 도출 - HITL 및 Shadow Mode 도입 (63% - 85%)
    yield _msg("graph_update", "Stage 4: Solutions Proposed (HITL Queue & Shadow Mode)", p=0.65, nodes=stage4_nodes, links=stage4_links)
    await asyncio.sleep(0.4)

    yield _msg("agent_post", "양측의 의견을 절충하기 위해, AI가 환불 초안과 RAG 매뉴얼 기반 판단 근거를 생성하되 최종 실행 전에 셀러나 상담원이 어드민 툴에서 '원클릭'으로 최종 승인을 하도록 만드는 'HITL(Human-in-the-Loop) 승인 대기 큐' 아키텍처를 제안합니다. 이 타협안은 어떻습니까?", "PM 김철수", "Product Manager", 0.67)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "의견을 이어서 구체화하자면, AI 판단 신뢰도가 85% 미만이거나 환불액이 50만 원을 초과할 경우 작동하는 'HITL 승인 대기 큐' UI를 제가 기획하겠습니다. AI가 RAG 근거와 요약본을 상담원 대시보드로 전달하고 상담원이 최종 확인 버튼을 누르게 설계하는 거죠.", "디자이너 정희채", "UI/UX Designer", 0.70)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "셀러가 최종 승인 버튼을 누르기 전에는 돈이 절대 빠져나가지 않는다면 대금 유출 보안성은 담보되겠네요. 하지만 매번 어드민 툴에 들어가서 복잡하게 확인해야 한다면 업무량이 너무 늘어납니다. 매일 수백 건을 어떻게 다 봅니까?", "셀러대표 민경아", "Seller Representative", 0.72)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "그 부분은 걱정 마세요! 셀러 전용 모바일 앱 및 알림톡을 연동해, AI가 판정한 RAG 근거 요약과 환불 대상 여부를 한눈에 시각화해 주고, 스마트폰에서 터치 한 번으로 3초 만에 승인할 수 있는 전용 간편 UI를 설계하겠습니다.", "디자이너 정희채", "UI/UX Designer", 0.74)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "스마트폰으로 3초 만에 RAG 근거를 보고 간편히 승인할 수 있다면, 대금 유출 걱정도 없고 업무 편의성도 오히려 늘어나겠네요. 이 안이라면 찬성합니다. 저희 셀러들도 동참하겠습니다.", "셀러대표 민경아", "Seller Representative", 0.76)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "아주 훌륭한 타협점입니다! 최종 결정 주체가 인간(셀러/상담원)이 되므로, AI 오작동에 대한 계약서 상 법률 책임 소재가 기존 임직원 과실 범위 내로 온전히 환원됩니다. 법적 리스크가 깔끔하게 해소되네요.", "법무팀장 최윤서", "Legal Counsel", 0.78)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "실제 배포 전 안정성 입증을 위해 추가 방안을 제안합니다. 9월 GA 출시 전에 '4주간의 Shadow Mode(섀도우 테스트)' 검증 단계를 로드맵에 못 박읍시다. 실제 결제 취소를 날리지는 않지만, 가상으로 백그라운드에서 AI의 응답 정확도와 PII 마스킹 속도를 실트래픽 로그 기반으로 검증하는 과도기입니다.", "아키텍트 박팀장", "Lead Architect", 0.81)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "좋습니다! 체감 속도를 보강하기 위해 한아름 엔지니어님 의견처럼 마스킹 처리 시 사용자에게 대기 UI를 연출합시다. '보안 필터 가동 중...' 및 '데이터 안심 마스킹 중'과 같은 시각적 로더 애니메이션을 아름답게 배치하면 UX 답답함을 완벽히 풀 수 있습니다.", "디자이너 정희채", "UI/UX Designer", 0.84)
    await asyncio.sleep(1.2)

    # 5단계: 합의 도달 및 최종 로드맵 확정 (85% - 100%)
    yield _msg("graph_update", "Stage 5: Final Consensus & Roadmap Locked", p=0.86, nodes=final_nodes, links=final_links)
    await asyncio.sleep(0.4)

    yield _msg("agent_post", "섀도우 모드가 도입된다면 QA팀 입장에서도 매우 든든합니다! RAG의 HWP 표 파싱 성공률과 오류 이탈 통계를 4주 동안 실데이터 기반으로 모니터링하여, 프로덕션 배포 전 환각율 3% 미만을 무결하게 입증해 보이겠습니다.", "QA매니저 강혜원", "Quality Assurance Lead", 0.88)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "저 역시 Shadow Mode 기간 동안 실제로 데이터가 저장되지 않는지(Zero-Retention)와 50ms 미만 마스킹 레이턴시 실측 데이터를 볼 수 있어 다행입니다. 보안 감사 승인을 처리하겠습니다.", "보안감사관 이지훈", "Security Auditor", 0.90)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "섀도우 테스트 결과서와 PII 50ms 미만 지연 데이터가 완비되면 B2B 영업 시 기업 고객사와 금융권의 까다로운 보안 심의를 초고속으로 통과할 수 있어, 런칭 즉시 3곳 이상의 대형 이커머스 계약 클로징이 가능해집니다.", "영업팀장 오세현", "B2B Sales Lead", 0.92)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "섀도우 모드 기간을 활용해 실시간 모니터링 대시보드가 현장에 안착되면, 단순 반복 작업에 치이던 기존 CS 상담원들의 역할을 'AI 승인 검토자(Auditor)'로 자연스럽게 전환하고 직무 등급을 상향할 수 있습니다. CS 노조 및 사내 HR 갈등의 리스크를 완벽하게 해소할 수 있겠네요. 적극 찬성합니다.", "CS/HR 서진우", "CS & HR Manager", 0.94)
    await asyncio.sleep(1.2)

    yield _msg("agent_post", "서진우 매니저님의 HR 업스킬링 로드맵 교육 비용과 정희채 디자이너님의 HITL 모바일 위젯 개발 공수를 PRD 최종 딜리버리 항목에 정식 결합하고 이를 최종 예산안에 반영하겠습니다. 30% 운영 비용 ROI가 가시화되었네요.", "PM 김철수", "Product Manager", 0.96)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "인프라 쪽에서도 섀도우 모드 동안 다중 LLM Failover 시나리오와 SLA 99.9% 가용성 실측치를 도출해 장애 제로 인프라를 보증하겠습니다. 비용이 약간 늘더라도 ROI 달성에는 문제없게 튜닝하겠습니다.", "SRE 한상민", "Site Reliability Engineer", 0.98)
    await asyncio.sleep(1.1)

    yield _msg("agent_post", "팀 여러분, 치열한 논쟁 끝에 보안 마스킹, HITL 승인 대기 큐, 섀도우 모드 및 HR 업스킬링 계획을 모두 통합한 완벽한 안전 자율 실행 플랫폼의 PRD 표준을 수립했습니다. 2026년 9월 B2B 시장의 거대한 성공을 확신합니다!", "PM 김철수", "Product Manager", 0.99)
    await asyncio.sleep(0.8)
    
    yield _msg("system_log", "Synthesizing full multi-stakeholder debate interactions... Complete.", p=1.0)
    await asyncio.sleep(0.4)
    yield _msg("simulation_complete", "All 12 stakeholder agents have reached a rigorous architectural and operational consensus.")

@router.get("/stream")
async def stream_simulation():
    """SSE stream yielding agent activities and graph updates."""
    if settings.mirofish_mode != "live":
        return StreamingResponse(_simulation_event_generator(mode="mock", reason="Validation mode is set to mock in settings"), media_type="text/event-stream")
    
    sim_id = session_state.get("simulation_id")
    if not sim_id:
        return StreamingResponse(_simulation_event_generator(mode="mock", reason="No active simulation session initialized. Call start simulation first."), media_type="text/event-stream")

    # Live Mode Connection check and Polling with Graceful Fallback
    import httpx
    try:
        # Check connection to MiroFish API engine first
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.mirofish_base_url}/health")
            resp.raise_for_status()
    except Exception as ec:
        logger.warning(f"MiroFish Engine is unreachable ({ec}). Gracefully falling back to 12-agent enterprise Mock stream.")
        return StreamingResponse(_simulation_event_generator(mode="live_fallback", reason=f"Engine Unreachable: {str(ec)}"), media_type="text/event-stream")

    async def _mirofish_event_generator():
        import json
        yield f'data: {json.dumps({"type": "mode_check", "mode": "live"})}\n\n'
        
        graph_id = session_state.get("graph_id")
        
        async def send_graph_update(progress_val: float = 0.0):
            if not graph_id:
                return None
            try:
                raw_graph = await mirofish.get_graph_data(graph_id)
                if not raw_graph:
                    return None
                
                fe_nodes = []
                fe_links = []
                
                label_to_group = {
                    "agent": 0,
                    "stakeholder": 0,
                    "risk": 1,
                    "solution": 2,
                    "alternative": 2,
                    "requirement": 3,
                    "fact": 4
                }
                
                for nd in raw_graph.get("nodes", []):
                    node_id = nd.get("uuid") or nd.get("name")
                    node_label = nd.get("name")
                    
                    group = 4
                    nd_labels = nd.get("labels", [])
                    for l in nd_labels:
                        l_lower = str(l).lower()
                        if l_lower in label_to_group:
                            group = label_to_group[l_lower]
                            break
                            
                    fe_nodes.append({
                        "id": node_id,
                        "label": node_label,
                        "group": group,
                        "summary": nd.get("summary", "")
                    })
                    
                for ed in raw_graph.get("edges", []):
                    source = ed.get("source_node_uuid")
                    target = ed.get("target_node_uuid")
                    if source and target:
                        fe_links.append({
                            "source": source,
                            "target": target,
                            "label": ed.get("name") or ed.get("fact_type", "")
                        })
                        
                return f'data: {json.dumps({"type": "graph_update", "nodes": fe_nodes, "links": fe_links, "progress": progress_val, "mode": "live"})}\n\n'
            except Exception as ge:
                logger.error(f"Failed to compile graph_update event: {ge}")
                return None

        # Emit initial graph structure immediately on connection
        initial_graph = await send_graph_update(0.01)
        if initial_graph:
            yield initial_graph

        try:
            async for event in mirofish.poll_events(sim_id):
                event["mode"] = "live"
                yield f'data: {json.dumps(event)}\n\n'
                
                # Emit graph update alongside agent posts to reflect Neo4j updates in real-time
                if event.get("type") == "agent_post":
                    graph_event = await send_graph_update(event.get("progress", 0.0))
                    if graph_event:
                        yield graph_event
        except Exception as e:
            logger.error(f"Error during MiroFish live event polling: {e}. Switching to Mock stream.")
            # Notify frontend of fallback mid-stream
            yield f'data: {json.dumps({"type": "mode_check", "mode": "live_fallback", "reason": f"Event Polling Error: {str(e)}"})}\n\n'
            # Yield remaining mock events for graceful completion
            async for mock_data in _simulation_event_generator(mode="live_fallback", reason=f"Event Polling Error: {str(e)}"):
                # Skip the first mode_check or logs if they clash
                if "mode_check" in mock_data or "Live Engine Fallback" in mock_data:
                    continue
                yield mock_data

    return StreamingResponse(_mirofish_event_generator(), media_type="text/event-stream")


@router.get("/{sim_id}/result")
async def get_simulation_result(sim_id: str):
    """Fetch completed simulation dialogue logs."""
    return {"sim_id": sim_id, "logs": [], "summary": "Simulation result placeholder"}

@router.post("/{sim_id}/report")
async def generate_report(sim_id: str):
    """Trigger the ReportAgent to generate a Markdown report."""
    if settings.mirofish_mode != "live":
        session_state["report_task_id"] = "mock_task_123"
        return {"status": "generating", "task_id": "mock_task_123"}
        
    try:
        resp = await mirofish.generate_report(sim_id)
        task_id = resp.get("data", {}).get("task_id", "")
        session_state["report_task_id"] = task_id
        return {"status": "generating", "task_id": task_id}
    except Exception as e:
        logger.error(f"Failed to trigger report: {e}")
        if settings.mirofish_fallback_to_mock:
            session_state["report_task_id"] = "mock_task_fallback"
            return {"status": "generating", "task_id": "mock_task_fallback"}
        raise HTTPException(status_code=500, detail=str(e))

async def _report_event_generator():
    """Mock SSE stream for report generation with highly premium quality insights."""
    import json
    def _msg(data):
        return f'data: {json.dumps(data)}\n\n'

    yield _msg({"type": "planning", "outline": ["01 Risks", "02 Scope adjustments", "03 Final Recommendations"]})
    await asyncio.sleep(1.5)
    
    yield _msg({"type": "section_start", "section_id": 1, "title": "01 Risks"})
    await asyncio.sleep(1.5)
    yield _msg({"type": "section_complete", "section_id": 1})
    await asyncio.sleep(1.0)
    
    yield _msg({"type": "section_start", "section_id": 2, "title": "02 Scope adjustments"})
    await asyncio.sleep(1.5)
    yield _msg({"type": "section_complete", "section_id": 2})
    await asyncio.sleep(1.0)

    yield _msg({"type": "section_start", "section_id": 3, "title": "03 Final Recommendations"})
    await asyncio.sleep(1.5)
    yield _msg({"type": "section_complete", "section_id": 3})
    await asyncio.sleep(1.0)

    markdown = """# 📊 MiroFish 시뮬레이션 검증 보고서
    
## 1. 핵심 리스크 및 잠재적 취약점 (Top Risks)
- 🔒 **데이터 프라이버시 우려 (Data Privacy Concern)**: B2B 고객사(이영희 대표)는 입력된 사내 기밀 및 프롬프트가 외부 LLM 학습에 활용될 수 있다는 치명적 우려를 제기하였습니다.
- ⚙️ **기능 설계 대비 공수 증가 (Scope Creep)**: FR-02(구조화된 데이터 추출)에 사용자 톤앤매너 스타일 가이드를 직접 결합하면서 기술적 복잡도가 상승하고 개발 일정이 20% 이상 지연될 위험이 감지되었습니다.
- 📉 **실질적 가치 훼손 가능성 (UX Friction)**: 생성된 PRD가 회사 가이드라인과 100% 매칭되지 않을 경우, 현업 사용자가 수동으로 대량 편집을 가해야 하므로 '30분 내 초안 완성'이라는 제품의 본질적 가치 제안이 훼손될 수 있습니다.

## 2. 해결 방안 및 권장 설계 조정 (Proposed Solutions)
- **Zero-Retention API 및 PII 마스킹 레이어 도입**: B2B 고객의 보안 불신을 종식시키기 위해 데이터 미보존 처리 및 개인식별정보(PII) 난독화 레이어를 설계서에 긴급 명시합니다.
- **RAG 기반 톤 메모리 아키텍처 적용**: 비용 증가와 과도한 파인튜닝 없이 고품질 맞춤형 톤을 구현할 수 있도록, 기존 사용자의 고품질 문서를 검색 증강 생성(RAG) 방식으로 참고하게 설계합니다.
- **참고 문서 업로드 UI 추가**: UI/UX Designer(정희채)의 의견을 수용하여, 대화창 내에 사내 스타일 가이드를 자유롭게 Drag & Drop하여 주입할 수 있는 UI를 MVP 범위에 추가합니다.

## 3. 최종 권장 사항 (Final Recommendations)
- 본 프로젝트는 보안 및 RAG 적용 여부에 따라 도입 여부가 결정되므로, 다음 스프린트에서 **보안 레이어 설계 완료** 및 **RAG 프로토타입 작성**을 최우선 Task로 승격할 것을 강력히 권고합니다.
"""
    yield _msg({"type": "report_complete", "markdown": markdown})

@router.get("/{sim_id}/report/stream")
async def stream_report(sim_id: str):
    """SSE stream yielding report generation progress and final markdown."""
    if settings.mirofish_mode != "live":
        return StreamingResponse(_report_event_generator(), media_type="text/event-stream")
        
    task_id = session_state.get("report_task_id")
    
    # Auto-trigger report if task_id not initialized
    if not task_id:
        try:
            resp = await mirofish.generate_report(sim_id)
            task_id = resp.get("data", {}).get("task_id", "")
            session_state["report_task_id"] = task_id
        except Exception as e:
            logger.error(f"Failed to auto-trigger report generation: {e}")
            if settings.mirofish_fallback_to_mock:
                return StreamingResponse(_report_event_generator(), media_type="text/event-stream")
            raise HTTPException(status_code=500, detail=f"Cannot start report generation: {str(e)}")

    async def _mirofish_report_event_generator():
        import json
        import re
        
        last_progress = 0
        attempts = 0
        max_attempts = settings.mirofish_max_polling
        
        # Keep track of active sections to mock the UI progression appropriately
        active_sections = {}
        outline = ["01 Risks", "02 Scope adjustments", "03 Action plan"]
        
        yield f'data: {json.dumps({"type": "planning", "outline": outline})}\n\n'
        await asyncio.sleep(0.5)

        while attempts < max_attempts:
            try:
                status_resp = await mirofish.get_report_status(task_id=task_id, simulation_id=sim_id)
                task_data = status_resp.get("data", {})
                status = task_data.get("status")
                progress = task_data.get("progress", last_progress)
                message = task_data.get("message", "Processing...")
                
                # Check for active stage in the message e.g. "[01 Risks] starting..."
                # to trigger visual section updates in frontend
                stage_match = re.search(r"\[(.*?)\]", message)
                if stage_match:
                    stage_title = stage_match.group(1)
                    # Find index in outline
                    sec_id = -1
                    for idx, title in enumerate(outline):
                        if stage_title in title or title in stage_title:
                            sec_id = idx + 1
                            break
                    if sec_id != -1 and sec_id not in active_sections:
                        # Complete previous active section if any
                        for prev_sec in list(active_sections.keys()):
                            if active_sections[prev_sec] == "running":
                                yield f'data: {json.dumps({"type": "section_complete", "section_id": prev_sec})}\n\n'
                                active_sections[prev_sec] = "complete"
                        
                        yield f'data: {json.dumps({"type": "section_start", "section_id": sec_id, "title": stage_title})}\n\n'
                        active_sections[sec_id] = "running"

                if status == "completed" or progress >= 100:
                    # Complete all remaining active sections
                    for sec in list(active_sections.keys()):
                        if active_sections[sec] == "running":
                            yield f'data: {json.dumps({"type": "section_complete", "section_id": sec})}\n\n'
                            active_sections[sec] = "complete"
                            
                    # Fetch finalized report content
                    report_resp = await mirofish.get_report_by_simulation(sim_id)
                    report_data = report_resp.get("data", {})
                    markdown_content = report_data.get("markdown_content") or "## Simulation Report\n\nNo content generated."
                    
                    yield f'data: {json.dumps({"type": "report_complete", "markdown": markdown_content})}\n\n'
                    break
                    
                elif status == "failed":
                    error_msg = task_data.get("error", "Generation failed")
                    err_md = f"## ⚠️ Report Generation Failed\n\n{error_msg}"
                    yield f'data: {json.dumps({"type": "report_complete", "markdown": err_md})}\n\n'
                    break
                else:
                    # Generic progress update (will be captured as standard logs in console/console panel)
                    yield f'data: {json.dumps({"type": "progress", "progress": progress / 100.0, "message": message})}\n\n'
                    last_progress = progress
                    
            except Exception as e:
                logger.error(f"Error polling report status: {e}")
                # Don't break immediately on network glitch, try to retry
                yield f'data: {json.dumps({"type": "progress", "progress": last_progress / 100.0, "message": f"Connection glitch, retrying... ({str(e)})"})}\n\n'
                
            await asyncio.sleep(settings.mirofish_polling_interval)
            attempts += 1
            
        else:
            yield f'data: {json.dumps({"type": "report_complete", "markdown": "## ⚠️ Report Generation Timed Out"})}\n\n'

    return StreamingResponse(_mirofish_report_event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /simulation/quick-start — Demo fast-track jump API
# ---------------------------------------------------------------------------

from pydantic import BaseModel

class QuickStartRequest(BaseModel):
    session_id: str
    project_id: str

@router.post("/quick-start")
async def quick_start_simulation(body: QuickStartRequest):
    """
    Directly inject the complete Simply AI Agent PRD and 7 stakeholders into the session,
    fast-forwarding the phase to 'ready_for_validation' immediately.
    """
    from app.services.session_store import session_store, SessionState, ConversationTurn
    
    # 1. Define complete Simply AI Agent PRD with 7 stakeholders preloaded
    rich_prd = {
      "schema_version": "0.1.0",
      "metadata": {
        "project_id": body.project_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "language": "ko-KR",
        "status": "ready_for_validation",
        "source": {
          "mode": "chat",
          "session_id": body.session_id
        },
        "version": "1.0"
      },
      "product": {
        "name": "Simply AI Agent",
        "one_liner": "단순 답변을 넘어 기업 레거시와 연동하여 실질적인 자율 Action을 안전하게 완수하는 B2B 기업용 AI 에이전트",
        "category": "B2B Enterprise AI Agent Platform",
        "platforms": ["web", "api"],
        "stage": "idea"
      },
      "users": {
        "primary_personas": [
          {
            "name": "최종 고객 (End User)",
            "role": "최종 고객",
            "goals": ["대기 시간 없이 배송조회, 환불, 취소 등의 액션을 즉각 완수한다."],
            "pain_points": ["상담원 연결 대기 시간이 너무 길다.", "단순 챗봇이 영혼 없이 같은 말만 반복해서 답답하다."]
          },
          {
            "name": "CS 운영 관리자 (CS Lead)",
            "role": "CS 운영 관리자",
            "goals": ["운영 비용을 30% 절감한다.", "TCR(업무 완결율) 40% 이상을 유지하면서 실시간 상담 자동화 비중을 높인다."],
            "pain_points": ["단순 반복 문의로 인한 업무 피로도가 높다.", "자동화율과 상담 만족도의 균형을 잡기 어렵다."]
          },
          {
            "name": "IT 보안 담당자 (SISO)",
            "role": "IT 보안 담당자",
            "goals": ["외부 LLM 연동 시 주민번호, 계좌 등 민감 개인정보(PII) 유출을 원천 봉쇄한다."],
            "pain_points": ["임직원 및 고객이 프롬프트에 기밀 데이터를 흘릴까 봐 불안하다.", "기존 마스킹 도구의 레이턴시(지연시간)가 너무 길다."]
          }
        ],
        "non_targets": ["연동할 백엔드 시스템이 아예 없는 소규모 SMB 소상공인", "보안 및 실시간성에 대한 요구사항이 전혀 없는 단순 웹 서비스"]
      },
      "problem": {
        "core_problem": "기존의 AI 챗봇은 단순 안내성 답변에 머물러 실제 주문 취소나 환불 등의 업무(Action)를 자율 수행하지 못하며 B2B 환경의 보안 규제를 준수하지 못함",
        "pain_points": [
          "실행(Action) 기능 부재로 결국 상담원 개입 필요",
          "외부 LLM 호출 시 민감정보(PII) 유출 보안 위험",
          "매뉴얼(HWP 등) 내부의 표(Table) 인식을 하지 못해 환각(Hallucination) 빈발"
        ],
        "current_alternatives": ["Notion 템플릿 안내 챗봇", "상담원 100% 수동 배정 처리"]
      },
      "solution": {
        "summary": "Agentic Intelligence (MCP)와 고속 PII Masking 보안 레이어를 결합한 안전한 엔터프라이즈 자율 실행 에이전트 시스템",
        "value_proposition": "이커머스/금융 시스템과 표준 MCP로 안전하게 연동해 자율 업무를 수행하고, 50ms PII 마스킹과 HITL 승인 대기 큐로 완벽한 보안 통제를 달성합니다.",
        "key_features": [
          {
            "name": "MCP 기반 자율 액션 처리 (HITL)",
            "description": "배송조회, 주문취소, 50만원 이하 자율 환불을 처리하며, 판단 불가 또는 고액 건은 승인 대기 큐로 상담원에게 토스(HITL)함.",
            "priority": "must_have"
          },
          {
            "name": "K-Security (50ms PII 마스킹)",
            "description": "50ms 이내 초고속 개인식별정보(PII) 마스킹 필터 레이어 장착 및 Zero-Retention 협약 적용.",
            "priority": "must_have"
          },
          {
            "name": "K-RAG HWP 표 파싱 엔진",
            "description": "HWP 내 복잡한 표(Table) 구조를 마크다운/JSON으로 완벽 분석하여 RAG 환각율을 3% 미만으로 억제함.",
            "priority": "must_have"
          }
        ]
      },
      "scope": {
        "mvp_in_scope": [
          "이커머스 3대 시나리오(조회, 취소, 50만원 이하 환불) 자율 액션",
          "50ms 고속 PII 마스킹 필터 레이어",
          "표준 MCP 프로토콜 연동 규격",
          "HITL 상담원 승인/반려 대시보드 및 HWP 표 파싱 엔진"
        ],
        "out_of_scope": [
          "음성 AI(Voicebot) 직접 연동",
          "다국어 글로벌 대응",
          "비표준 레거시 시스템 전용 커스텀 어댑터 개발"
        ]
      },
      "requirements": {
        "functional": [
          {
            "id": "FR-01",
            "statement": "AI 에이전트는 환불 건이 50만 원 이상이거나 판단 불능일 때 즉시 HITL 승인 큐로 summary와 근거를 토스해야 한다.",
            "priority": "critical"
          },
          {
            "id": "FR-02",
            "statement": "HWP 파서 엔진은 표 내부의 셀 병합 데이터를 유실 없이 마크다운 표로 직렬화하여 RAG 컨텍스트에 주입해야 한다.",
            "priority": "high"
          }
        ],
        "non_functional": [
          {
            "id": "NFR-01",
            "statement": "End-to-End 전체 시스템 응답 속도는 1.5초~2.0초 이내여야 한다 (TTFT 800ms 포함).",
            "priority": "critical"
          },
          {
            "id": "NFR-02",
            "statement": "ISMS-P 및 CSAP 공공 보안 인증 규격을 완벽히 준수할 수 있는 데이터 미저장 아키텍처를 지원해야 한다.",
            "priority": "critical"
          }
        ]
      },
      "success_metrics": {
        "north_star": "에이전트 업무 완결율 (TCR) 40% 달성",
        "product_metrics": [
          {
            "name": "상담 운영 비용 절감율",
            "target": "30% 이상"
          },
          {
            "name": "E2E Latency 1.5초 준수율",
            "target": "95% 이상"
          }
        ],
        "guardrail_metrics": [
          {
            "name": "근거 기반 정확도 (Grounding Score)",
            "target": "환각률 3% 미만 감시"
          }
        ]
      },
      "delivery": {
        "priority": "high",
        "timeline_confidence": "medium",
        "target_release": "2026-09-01"
      },
      "assumptions": [
        {
          "text": "고객사가 액션 처리를 위한 표준 RESTful API를 안정적으로 제공한다."
        }
      ],
      "risks": [
        {
          "title": "Latency 지연 위험",
          "description": "네트워크 통신 지연으로 1.5초 응답 성능 준수가 저해될 우려가 있음.",
          "severity": "high",
          "mitigation": "비동기 액션 처리 및 중간 로딩 멘트 주입 설계 도입"
        }
      ],
      "open_questions": [
        {
          "text": "TCR 성과 기반의 구독형 라이선스 모델 도입 시 최종 단가와 정산 주기 결정 필요"
        }
      ],
      "validation": {
        "goals": [
          "50ms PII 마스킹이 금융권 보안 규제 요건을 충족하는지 검증한다.",
          "HWP 표 파싱의 정확도 향상으로 인한 RAG 신뢰성을 최종 입증한다."
        ],
        "stakeholder_personas": [
          {
            "name": "PM 김철수 (Product Manager)",
            "role": "Product Manager",
            "review_angle": "비즈니스 가치 극대화 및 MVP 조기 런칭"
          },
          {
            "name": "개발 아키텍트 박팀장 (Lead Architect)",
            "role": "Lead Architect",
            "review_angle": "표준 MCP 확장성 및 HWP 파싱 안전성"
          },
          {
            "name": "보안 감사관 이지훈 (Security Auditor)",
            "role": "Security Auditor",
            "review_angle": "Zero-Retention 및 50ms 이내 PII 마스킹 규정 준수"
          },
          {
            "name": "법무 팀장 최윤서 (Legal Counsel)",
            "role": "Legal Counsel",
            "review_angle": "AI 오작동 시 책임 소재 및 승인 프로세스 컴플라이언스"
          },
          {
            "name": "CFO 정우진 (Financial Director)",
            "role": "Financial Director",
            "review_angle": "토큰 비용 분석 및 TCR 연동 ROI 추산"
          },
          {
            "name": "QA 매니저 강혜원 (Quality Assurance Lead)",
            "role": "Quality Assurance Lead",
            "review_angle": "RAG 환각율 3% 미만 엣지 시나리오 검증"
          },
          {
            "name": "DevOps 전문가 한상민 (SRE Lead)",
            "role": "Site Reliability Engineer",
            "review_angle": "가용성(99.9%) 및 Failover 체계 안전성 검증"
          },
          {
            "name": "UI/UX 디자이너 정희채 (UI/UX Designer)",
            "role": "UI/UX Designer",
            "review_angle": "HITL 관리자 툴의 직관적인 사용자 저니 및 모니터링 시각화"
          },
          {
            "name": "프론트엔드 개발자 한아름 (Frontend Engineer)",
            "role": "Frontend Engineer",
            "review_angle": "50ms 마스킹 프론트엔드 렌더링 최적화 및 신뢰도 차트 바인딩"
          },
          {
            "name": "영업팀장 오세현 (B2B Sales Lead)",
            "role": "B2B Sales Lead",
            "review_angle": "대기업/금융권 딜 클로징을 위한 규제 증명 및 세일즈 파이프라인 개방 조건 검토"
          },
          {
            "name": "CS/HR 매니저 서진우 (CS & HR Manager)",
            "role": "CS & HR Manager",
            "review_angle": "AI 자동화율 40% 도달에 따른 상담원 직무 업스킬링 및 CS 노조 저항 조율"
          },
          {
            "name": "셀러대표 민경아 (Seller Representative)",
            "role": "Seller Representative",
            "review_angle": "50만원 이하 자율 환불 시 셀러 대금 유출 차단 및 플랫폼 신뢰성 정산 리스크 검증"
          }
        ],
        "simulation_requirement": "Simply AI Agent의 12개 전문가 도메인 입체 검증 및 상품 생태계 전체 밸류 체인 리스크 추출"
      }
    }

    # 2. Save complete state directly to session store
    state = session_store.get_session(body.session_id)
    if state is None:
        state = SessionState(session_id=body.session_id, project_id=body.project_id)
    
    state.turn_count = 5
    state.phase = "ready_for_validation"
    state.current_prd_draft = rich_prd
    
    # Overwrite history with quick start message for clean UX
    state.conversation_history = [
        ConversationTurn(
            role="user",
            content="⚡ [퀵스타트] Simply AI Agent 데모 PRD를 로드하고 즉시 시뮬레이션 단계로 진입합니다."
        ),
        ConversationTurn(
            role="assistant",
            content="알겠습니다. Simply AI Agent(가칭)의 완결된 B2B 엔터프라이즈 PRD 기획안과 상품개발/현업/C-level/이해관계자 생태계를 어우르는 12인의 다차원 전문가 그룹(PM, 아키텍트, 보안, 법무, CFO, QA, DevOps, 디자이너, 프론트엔드, 영업, CS/HR, 셀러대표)을 세션에 성공적으로 로드했습니다! 이제 정적 검증 및 시뮬레이션을 즉시 실행하실 수 있습니다."
        )
    ]
    
    session_store.save_session(state)
    
    return {
        "status": "success",
        "phase": state.phase,
        "prd": rich_prd
    }
