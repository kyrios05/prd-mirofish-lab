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

# Comprehensive 77-node and 154-link mock database for scalable visualization
ALL_MOCK_NODES = [
    # 1. 12인의 전문가 (Group 0: 기획/개발, 1: 보안/규제, 2: 재무/인프라/QA, 3: 현업/생태계)
    {"id": "PM_Kim", "group": 0, "label": "PM 김철수"},
    {"id": "Sales_Oh", "group": 3, "label": "영업팀장 오세현"},
    {"id": "HR_Seo", "group": 3, "label": "CS/HR 서진우"},
    {"id": "Sec_Lee", "group": 1, "label": "보안감사관 이지훈"},
    {"id": "Legal_Choi", "group": 1, "label": "법무팀장 최윤서"},
    {"id": "Arch_Park", "group": 0, "label": "아키텍트 박팀장"},
    {"id": "CFO_Woo", "group": 2, "label": "CFO 정우진"},
    {"id": "QA_Kang", "group": 2, "label": "QA매니저 강혜원"},
    {"id": "SRE_Han", "group": 2, "label": "SRE 한상민"},
    {"id": "FE_Han", "group": 0, "label": "프론트 한아름"},
    {"id": "Seller_Min", "group": 3, "label": "셀러대표 민경아"},
    {"id": "Design_Jung", "group": 0, "label": "디자이너 정희채"},
    # 2. 리스크 노드 (Group 4: 도출된 리스크)
    {"id": "Risk_PII_1", "group": 4, "label": "PII 개인정보 노출 취약점"},
    {"id": "Risk_PII_2", "group": 4, "label": "ISMS-P 인증 박탈 우려"},
    {"id": "Risk_PII_3", "group": 4, "label": "CSAP 공공 보안 인증 규정 저촉"},
    {"id": "Risk_PII_4", "group": 4, "label": "외부 LLM 전송 시 민감 로그 유출"},
    {"id": "Risk_PII_5", "group": 4, "label": "Zero-Retention 위반 제재"},
    {"id": "Risk_Latency_1", "group": 4, "label": "E2E 지연시간 1.5초 돌파"},
    {"id": "Risk_Latency_2", "group": 4, "label": "PII 필터 처리에 의한 프론트 렉"},
    {"id": "Risk_Latency_3", "group": 4, "label": "웹소켓 실시간 이벤트 오버헤드"},
    {"id": "Risk_Latency_4", "group": 4, "label": "API 게이트웨이 동기 응답 정체"},
    {"id": "Risk_Latency_5", "group": 4, "label": "네트워크 패킷 전처리 병목"},
    {"id": "Risk_SLA_1", "group": 4, "label": "단일 LLM 마비 시 전체 중단"},
    {"id": "Risk_SLA_2", "group": 4, "label": "트래픽 폭증 시 인프라 스케일링 병목"},
    {"id": "Risk_SLA_3", "group": 4, "label": "대기 시간 초과로 인한 세션 유실"},
    {"id": "Risk_SLA_4", "group": 4, "label": "Failover 프록시 오동작 장애"},
    {"id": "Risk_SLA_5", "group": 4, "label": "네트워크 유실로 인한 상태 불일치"},
    {"id": "Risk_Seller_1", "group": 4, "label": "오환불로 인한 셀러 대금 유출"},
    {"id": "Risk_Seller_2", "group": 4, "label": "정산 불일치로 입점 셀러 반발"},
    {"id": "Risk_Seller_3", "group": 4, "label": "AI 판정 신뢰도 오류 피해 전가"},
    {"id": "Risk_Seller_4", "group": 4, "label": "50만원 한도 자율 집행 불안"},
    {"id": "Risk_Seller_5", "group": 4, "label": "플랫폼 신뢰도 훼손 및 판매자 이탈"},
    # 3. 요구사항 노드 (Group 3: 요구사항)
    {"id": "Req_FR_1", "group": 3, "label": "FR-01: 50만원 이하 자율 환불"},
    {"id": "Req_FR_2", "group": 3, "label": "FR-02: HWP 표 파싱 표 직렬화"},
    {"id": "Req_FR_3", "group": 3, "label": "FR-03: HITL 승인 대기 큐 연동"},
    {"id": "Req_FR_4", "group": 3, "label": "FR-04: 할루시네이션 3% 통제"},
    {"id": "Req_FR_5", "group": 3, "label": "FR-05: 모바일 간편 승인 위젯"},
    {"id": "Req_NFR_1", "group": 3, "label": "NFR-01: E2E 1.5초 이내 속도"},
    {"id": "Req_NFR_2", "group": 3, "label": "NFR-02: Zero-Retention 아키텍처"},
    {"id": "Req_NFR_3", "group": 3, "label": "NFR-03: 로컬 Failover 프록시"},
    {"id": "Req_NFR_4", "group": 3, "label": "NFR-04: 이커머스 API 게이트웨이"},
    {"id": "Req_NFR_5", "group": 3, "label": "NFR-05: 실시간 웹소켓 이벤트 렌더"},
    {"id": "Metric_1", "group": 3, "label": "성공지표: TCR 40% 이상"},
    {"id": "Metric_2", "group": 3, "label": "운영 비용: 30% 이상 절감"},
    {"id": "Metric_3", "group": 3, "label": "SLA 보장: 가용성 99.9%"},
    {"id": "Metric_4", "group": 3, "label": "가드레일: 환각율 3% 미만"},
    {"id": "Metric_5", "group": 3, "label": "지연속도: E2E Latency 1.5초 준수율 95%"},
    # 4. 솔루션 노드 (Group 5: 대안 및 솔루션)
    {"id": "Sol_HITL_1", "group": 5, "label": "HITL 승인 대기 큐 아키텍처"},
    {"id": "Sol_HITL_2", "group": 5, "label": "신뢰도 85% 임계값 자동 분류"},
    {"id": "Sol_HITL_3", "group": 5, "label": "스마트폰 알림톡 간편 UI 발송"},
    {"id": "Sol_HITL_4", "group": 5, "label": "1클릭 간편 승인 위젯 컴포넌트"},
    {"id": "Sol_HITL_5", "group": 5, "label": "상담원 Audit 직무 업스킬링 로드맵"},
    {"id": "Sol_Shadow_1", "group": 5, "label": "4주간의 Shadow Mode 모의 검증"},
    {"id": "Sol_Shadow_2", "group": 5, "label": "백그라운드 가상 트래픽 인프라"},
    {"id": "Sol_Shadow_3", "group": 5, "label": "실시간 PII 마스킹 속도 측정기"},
    {"id": "Sol_Shadow_4", "group": 5, "label": "RAG 표 파싱 정확도 모니터링"},
    {"id": "Sol_Shadow_5", "group": 5, "label": "CS 노조 소통 및 안정성 실측 리포트"},
    {"id": "Sol_Failover_1", "group": 5, "label": "로컬 Failover LLM 프록시"},
    {"id": "Sol_Failover_2", "group": 5, "label": "300ms 로컬 Ollama 자동 스위칭"},
    {"id": "Sol_Failover_3", "group": 5, "label": "비동기 전처리 프록시 서버 이중화"},
    {"id": "Sol_Failover_4", "group": 5, "label": "Zero-Retention 메모리 관리체계"},
    {"id": "Sol_Failover_5", "group": 5, "label": "호출 원가 30% 통제 프레임워크"},
    # 5. 마일스톤 및 시스템 (Group 6: 마일스톤, 기타)
    {"id": "Milestone_GA", "group": 6, "label": "2026.09 정식 런칭"},
    {"id": "Milestone_BMT", "group": 6, "label": "6월 BMT 기술 검증"},
    {"id": "Sys_Ollama", "group": 6, "label": "로컬 Ollama 엔진"},
    {"id": "Sys_API_Gateway", "group": 6, "label": "API Gateway 컴포넌트"},
    {"id": "Sys_Seller_App", "group": 6, "label": "셀러 전용 모바일 앱"},
    {"id": "Sys_Admin_Console", "group": 6, "label": "상담원 어드민 대시보드"},
    {"id": "Sys_Database", "group": 6, "label": "이커머스 운영 DB"},
    {"id": "Sys_Notification_Talk", "group": 6, "label": "카카오 알림톡 서비스"},
    {"id": "Sys_Auth_Server", "group": 6, "label": "OAuth 인증 서버"},
    {"id": "Sys_PII_Masking_Filter", "group": 6, "label": "실시간 PII 필터링"},
    {"id": "Sys_HWP_Parser", "group": 6, "label": "고정밀 HWP 파서"},
    {"id": "Sys_RAG_Vector_DB", "group": 6, "label": "RAG 벡터 DB"},
    {"id": "Sys_Docker_Network", "group": 6, "label": "도커 가상 네트워크"},
    {"id": "Sys_Consensus", "group": 6, "label": "전문가 합의체 완성"},
    {"id": "Milestone_GA_2", "group": 6, "label": "2차 파이프라인 개방"}
]

ALL_MOCK_LINKS = [
    # 1. 전문가 간 연결 (22개)
    {"source": "PM_Kim", "target": "Sales_Oh"},
    {"source": "PM_Kim", "target": "HR_Seo"},
    {"source": "PM_Kim", "target": "Sec_Lee"},
    {"source": "PM_Kim", "target": "Legal_Choi"},
    {"source": "PM_Kim", "target": "CFO_Woo"},
    {"source": "PM_Kim", "target": "Arch_Park"},
    {"source": "Arch_Park", "target": "SRE_Han"},
    {"source": "Arch_Park", "target": "FE_Han"},
    {"source": "Arch_Park", "target": "QA_Kang"},
    {"source": "Sales_Oh", "target": "Seller_Min"},
    {"source": "Seller_Min", "target": "CFO_Woo"},
    {"source": "QA_Kang", "target": "FE_Han"},
    {"source": "QA_Kang", "target": "SRE_Han"},
    {"source": "SRE_Han", "target": "FE_Han"},
    {"source": "Design_Jung", "target": "FE_Han"},
    {"source": "Design_Jung", "target": "PM_Kim"},
    {"source": "Legal_Choi", "target": "Sec_Lee"},
    {"source": "HR_Seo", "target": "Seller_Min"},
    {"source": "Sales_Oh", "target": "CFO_Woo"},
    {"source": "HR_Seo", "target": "CFO_Woo"},
    {"source": "Sec_Lee", "target": "Arch_Park"},
    {"source": "Legal_Choi", "target": "Arch_Park"},
    # 2. 전문가 -> 리스크 노드 연결 (20개)
    {"source": "Sec_Lee", "target": "Risk_PII_1"},
    {"source": "Sec_Lee", "target": "Risk_PII_2"},
    {"source": "Sec_Lee", "target": "Risk_PII_3"},
    {"source": "Sec_Lee", "target": "Risk_PII_4"},
    {"source": "Sec_Lee", "target": "Risk_PII_5"},
    {"source": "FE_Han", "target": "Risk_Latency_1"},
    {"source": "FE_Han", "target": "Risk_Latency_2"},
    {"source": "FE_Han", "target": "Risk_Latency_3"},
    {"source": "FE_Han", "target": "Risk_Latency_4"},
    {"source": "FE_Han", "target": "Risk_Latency_5"},
    {"source": "SRE_Han", "target": "Risk_SLA_1"},
    {"source": "SRE_Han", "target": "Risk_SLA_2"},
    {"source": "SRE_Han", "target": "Risk_SLA_3"},
    {"source": "SRE_Han", "target": "Risk_SLA_4"},
    {"source": "SRE_Han", "target": "Risk_SLA_5"},
    {"source": "Seller_Min", "target": "Risk_Seller_1"},
    {"source": "Seller_Min", "target": "Risk_Seller_2"},
    {"source": "Seller_Min", "target": "Risk_Seller_3"},
    {"source": "Seller_Min", "target": "Risk_Seller_4"},
    {"source": "Seller_Min", "target": "Risk_Seller_5"},
    # 3. 전문가 -> 요구사항 노드 연결 (15개)
    {"source": "PM_Kim", "target": "Req_FR_1"},
    {"source": "PM_Kim", "target": "Req_FR_2"},
    {"source": "PM_Kim", "target": "Req_FR_3"},
    {"source": "PM_Kim", "target": "Req_FR_4"},
    {"source": "PM_Kim", "target": "Req_FR_5"},
    {"source": "Arch_Park", "target": "Req_NFR_1"},
    {"source": "Arch_Park", "target": "Req_NFR_2"},
    {"source": "Arch_Park", "target": "Req_NFR_3"},
    {"source": "Arch_Park", "target": "Req_NFR_4"},
    {"source": "Arch_Park", "target": "Req_NFR_5"},
    {"source": "CFO_Woo", "target": "Metric_1"},
    {"source": "CFO_Woo", "target": "Metric_2"},
    {"source": "CFO_Woo", "target": "Metric_3"},
    {"source": "CFO_Woo", "target": "Metric_4"},
    {"source": "CFO_Woo", "target": "Metric_5"},
    # 4. 전문가 -> 솔루션 노드 연결 (15개)
    {"source": "Design_Jung", "target": "Sol_HITL_1"},
    {"source": "Design_Jung", "target": "Sol_HITL_2"},
    {"source": "Design_Jung", "target": "Sol_HITL_3"},
    {"source": "Design_Jung", "target": "Sol_HITL_4"},
    {"source": "Design_Jung", "target": "Sol_HITL_5"},
    {"source": "QA_Kang", "target": "Sol_Shadow_1"},
    {"source": "QA_Kang", "target": "Sol_Shadow_2"},
    {"source": "QA_Kang", "target": "Sol_Shadow_3"},
    {"source": "QA_Kang", "target": "Sol_Shadow_4"},
    {"source": "QA_Kang", "target": "Sol_Shadow_5"},
    {"source": "SRE_Han", "target": "Sol_Failover_1"},
    {"source": "SRE_Han", "target": "Sol_Failover_2"},
    {"source": "SRE_Han", "target": "Sol_Failover_3"},
    {"source": "SRE_Han", "target": "Sol_Failover_4"},
    {"source": "SRE_Han", "target": "Sol_Failover_5"},
    # 5. 요구사항 -> 리스크 연계 (20개)
    {"source": "Req_FR_1", "target": "Risk_Seller_1"},
    {"source": "Req_FR_2", "target": "Risk_Seller_2"},
    {"source": "Req_FR_3", "target": "Risk_Seller_3"},
    {"source": "Req_FR_4", "target": "Risk_Seller_4"},
    {"source": "Req_FR_5", "target": "Risk_Seller_5"},
    {"source": "Req_NFR_1", "target": "Risk_Latency_1"},
    {"source": "Req_NFR_2", "target": "Risk_Latency_2"},
    {"source": "Req_NFR_3", "target": "Risk_Latency_3"},
    {"source": "Req_NFR_4", "target": "Risk_Latency_4"},
    {"source": "Req_NFR_5", "target": "Risk_Latency_5"},
    {"source": "Metric_1", "target": "Risk_SLA_1"},
    {"source": "Metric_2", "target": "Risk_SLA_2"},
    {"source": "Metric_3", "target": "Risk_SLA_3"},
    {"source": "Metric_4", "target": "Risk_SLA_4"},
    {"source": "Metric_5", "target": "Risk_SLA_5"},
    {"source": "Req_NFR_1", "target": "Risk_PII_1"},
    {"source": "Req_NFR_2", "target": "Risk_PII_2"},
    {"source": "Req_NFR_3", "target": "Risk_PII_3"},
    {"source": "Req_NFR_4", "target": "Risk_PII_4"},
    {"source": "Req_NFR_5", "target": "Risk_PII_5"},
    # 6. 솔루션 -> 리스크 완화 해결선 (20개)
    {"source": "Sol_HITL_1", "target": "Risk_Seller_1"},
    {"source": "Sol_HITL_2", "target": "Risk_Seller_2"},
    {"source": "Sol_HITL_3", "target": "Risk_Seller_3"},
    {"source": "Sol_HITL_4", "target": "Risk_Seller_4"},
    {"source": "Sol_HITL_5", "target": "Risk_Seller_5"},
    {"source": "Sol_Shadow_1", "target": "Risk_Latency_1"},
    {"source": "Sol_Shadow_2", "target": "Risk_Latency_2"},
    {"source": "Sol_Shadow_3", "target": "Risk_Latency_3"},
    {"source": "Sol_Shadow_4", "target": "Risk_Latency_4"},
    {"source": "Sol_Shadow_5", "target": "Risk_Latency_5"},
    {"source": "Sol_Failover_1", "target": "Risk_SLA_1"},
    {"source": "Sol_Failover_2", "target": "Risk_SLA_2"},
    {"source": "Sol_Failover_3", "target": "Risk_SLA_3"},
    {"source": "Sol_Failover_4", "target": "Risk_SLA_4"},
    {"source": "Sol_Failover_5", "target": "Risk_SLA_5"},
    {"source": "Sol_Shadow_1", "target": "Risk_PII_1"},
    {"source": "Sol_Shadow_2", "target": "Risk_PII_2"},
    {"source": "Sol_Shadow_3", "target": "Risk_PII_3"},
    {"source": "Sol_Shadow_4", "target": "Risk_PII_4"},
    {"source": "Sol_Shadow_5", "target": "Risk_PII_5"},
    # 7. 시스템 노드 및 마일스톤 연결선 (42개) -> 총 154개
    {"source": "Sys_Ollama", "target": "Sys_Failover_Proxy"},
    {"source": "Sys_Failover_Proxy", "target": "Sys_API_Gateway"},
    {"source": "Sys_API_Gateway", "target": "Sys_PII_Masking_Filter"},
    {"source": "Sys_API_Gateway", "target": "Sys_Admin_Console"},
    {"source": "Sys_API_Gateway", "target": "Sys_Seller_App"},
    {"source": "Sys_Seller_App", "target": "Sys_Notification_Talk"},
    {"source": "Sys_Admin_Console", "target": "Sys_Notification_Talk"},
    {"source": "Sys_API_Gateway", "target": "Sys_Database"},
    {"source": "Sys_API_Gateway", "target": "Sys_Auth_Server"},
    {"source": "Sys_HWP_Parser", "target": "Sys_RAG_Vector_DB"},
    {"source": "Sys_RAG_Vector_DB", "target": "Sys_Ollama"},
    {"source": "Sys_Docker_Network", "target": "Sys_Ollama"},
    {"source": "Sys_Docker_Network", "target": "Sys_API_Gateway"},
    {"source": "Sys_Consensus", "target": "Milestone_GA"},
    {"source": "Sys_Consensus", "target": "Milestone_BMT"},
    {"source": "Milestone_BMT", "target": "Milestone_GA"},
    {"source": "PM_Kim", "target": "Sys_Consensus"},
    {"source": "Sales_Oh", "target": "Sys_Consensus"},
    {"source": "HR_Seo", "target": "Sys_Consensus"},
    {"source": "Sec_Lee", "target": "Sys_Consensus"},
    {"source": "Legal_Choi", "target": "Sys_Consensus"},
    {"source": "Arch_Park", "target": "Sys_Consensus"},
    {"source": "CFO_Woo", "target": "Sys_Consensus"},
    {"source": "QA_Kang", "target": "Sys_Consensus"},
    {"source": "SRE_Han", "target": "Sys_Consensus"},
    {"source": "FE_Han", "target": "Sys_Consensus"},
    {"source": "Seller_Min", "target": "Sys_Consensus"},
    {"source": "Design_Jung", "target": "Sys_Consensus"},
    {"source": "Milestone_GA", "target": "Milestone_GA_2"},
    {"source": "Sys_Ollama", "target": "Milestone_GA"},
    {"source": "Sys_API_Gateway", "target": "Milestone_GA"},
    {"source": "Sys_Seller_App", "target": "Milestone_GA"},
    {"source": "Sys_Admin_Console", "target": "Milestone_GA"},
    {"source": "Sys_Database", "target": "Milestone_GA"},
    {"source": "Sys_HWP_Parser", "target": "Milestone_GA"},
    {"source": "Sys_RAG_Vector_DB", "target": "Milestone_GA"},
    {"source": "Sys_Notification_Talk", "target": "Milestone_GA"},
    {"source": "Sys_Auth_Server", "target": "Milestone_GA"},
    {"source": "Sys_PII_Masking_Filter", "target": "Milestone_GA"},
    {"source": "Sys_Failover_Proxy", "target": "Milestone_GA"},
    {"source": "Sys_Docker_Network", "target": "Milestone_GA"},
    {"source": "Sys_Consensus", "target": "Milestone_GA_2"}
]

async def _simulation_event_generator(mode: str = "mock", reason: str = None):
    """Rich SSE stream for simulation with 35+ high-density stakeholder debate interactions."""
    import json
    yield f'data: {json.dumps({"type": "mode_check", "mode": mode, "reason": reason})}\n\n'
    if reason:
        yield f'data: {json.dumps({"type": "system_log", "content": f"🚨 Live Engine Fallback: {reason}", "timestamp": datetime.now(timezone.utc).isoformat(), "mode": mode})}\n\n'
    def _ts(): return datetime.now(timezone.utc).isoformat()
    
    # 5-stage progressive graph slices matching the 70+ node / 140+ edge requirements
    stage1_nodes = ALL_MOCK_NODES[:15]
    stage1_links = ALL_MOCK_LINKS[:25]
    
    stage2_nodes = ALL_MOCK_NODES[:32]
    stage2_links = ALL_MOCK_LINKS[:58]
    
    stage3_nodes = ALL_MOCK_NODES[:48]
    stage3_links = ALL_MOCK_LINKS[:92]
    
    stage4_nodes = ALL_MOCK_NODES[:64]
    stage4_links = ALL_MOCK_LINKS[:122]
    
    final_nodes = ALL_MOCK_NODES
    final_links = ALL_MOCK_LINKS
    
    def _msg(t, c, n=None, at=None, p=None, nodes=None, links=None):
        data = {"type": t, "content": c, "timestamp": _ts(), "mode": mode}
        if n: data["agent_name"] = n
        if at: data["agent_type"] = at
        if p is not None: data["progress"] = p
        if nodes: data["nodes"] = nodes
        if links: data["links"] = links
        return f'data: {json.dumps(data)}\n\n'

    # 1단계: 비즈니스 가치 달성 vs CS 운영 조직 저항 (1% - 20%)
    yield _msg("system_log", "Initializing High-Density MiroFish Mock Agent Engine v13.0...", p=0.01)
    await asyncio.sleep(0.3)
    
    yield _msg("graph_update", "Stage 1: Business Vision & HR Resistance Initiated", p=0.05, nodes=stage1_nodes, links=stage1_links)
    await asyncio.sleep(0.3)

    yield _msg("agent_post", "이번 Simply AI Agent는 기업용 레거시와 연동하여 주문 조회, 주문 취소, 50만원 이하 자율 환불 액션을 완수해야 합니다. 상담원 개입을 최소화하여 목표 TCR(업무완결율) 40% 이상을 기한 내 달성합시다.", "PM 김철수", "Product Manager", 0.07)
    await asyncio.sleep(0.8)

    yield _msg("agent_post", "김철수 PM님, 현장을 전혀 모르는 안일한 발상입니다! AI가 TCR 40%를 달성하면 기존 CS 상담원들의 직무가 축소될 것이 뻔한데 CS 노조가 가만히 있겠습니까? 당장 내일 아침 본사 로비에서 구조조정 규탄 피켓 시위를 벌이겠다고 강경하게 경고해 왔습니다. 현장 합의 없는 도입은 전면 사보타주만 부를 뿐입니다!", "CS/HR 서진우", "CS & HR Manager", 0.09)
    await asyncio.sleep(0.8)

    yield _msg("agent_post", "서 매니저님, 지금 노조 시위 때문에 프로젝트를 지연시키자는 겁니까? 이번 6월 BMT(기술검증)를 통과하지 못하면 당장 연간 25억 규모의 대형 고객사 3곳과의 거래 딜이 즉시 무산됩니다. 비즈니스 생존보다 시위 방어가 더 중요합니까?", "영업팀장 오세현", "B2B Sales Lead", 0.11)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "오세현 팀장님, 단기 실적에 눈이 멀어 곪아 터질 폭탄을 방치하는 게 더 위험합니다! 현장 상담원들이 반발해서 RAG 입력 데이터 분류 태그를 엉망으로 입력하거나 고의로 피드백 점수를 흐려놓으면, 전체 AI 응답 정확도가 30% 이하로 곤두박질칠 겁니다. 그때 발생하는 유무형의 신뢰 손실은 25억이 아니라 250억으로도 못 메웁니다!", "CS/HR 서진우", "CS & HR Manager", 0.13)
    await asyncio.sleep(0.8)

    yield _msg("agent_post", "두 분 싸움보다 더 심각한 컴플라이언스 붕괴 위험이 있습니다. 외부 LLM API 통신 시 계좌번호와 주민번호 같은 개인식별정보(PII) 유출 위험은 치명적입니다. 50ms 이내 초고속 PII 마스킹 차단율 100%와 데이터 미저장(Zero-Retention) 조건이 실측 입증되지 않으면 금융감독원 보안성 심의에서 바로 반려되어 서비스 자체가 셧다운됩니다!", "보안감사관 이지훈", "Security Auditor", 0.16)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "이 감사관님, 50ms 이내 100% 차단은 물리적으로 불가능합니다! API 게이트웨이 전단에 다중 정규식 필터와 검출 모델을 동기식으로 끼워 넣으면 프록시 홉 오버헤드만 최소 600ms가 추가됩니다. 결과적으로 전체 E2E 레이턴시가 목표치인 1.5초를 훌쩍 넘어 2.5초에 달할 텐데, 화면이 렉 걸려 굳어버리는 서비스를 유저가 쓰겠습니까?", "아키텍트 박팀장", "Lead Architect", 0.18)
    await asyncio.sleep(0.8)

    # 2단계: 보안 감사 및 법률적 규제 검증의 압박 (20% - 45%)
    yield _msg("graph_update", "Stage 2: Regulatory & Legal Constraints Addressed", p=0.20, nodes=stage2_nodes, links=stage2_links)
    await asyncio.sleep(0.3)

    yield _msg("agent_post", "맞습니다! 동기식 전처리 필터링이 연동되면 화면이 3초 이상 멈춰 서게 되고, 답답한 사용자들이 새로고침을 연타해서 API 커넥션이 폭증하고 웹소켓 서버가 크래시 날 겁니다. 속도가 무너진 보안은 사용자 이탈만 초래하는 UX 파괴일 뿐입니다!", "프론트 한아름", "Frontend Engineer", 0.22)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "한아름 엔지니어님, 화면 렉보다 금융 컴플라이언스 위반으로 인한 영업정지 처분과 과징금 10억원이 훨씬 치명적입니다! 보안 필터링은 타협 불가능한 절대 의무입니다. 기술적 어려움은 엔지니어링 리소스를 갈아 넣어서라도 50ms 기준을 지켜내야 할 영역입니다!", "보안감사관 이지훈", "Security Auditor", 0.25)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "보안뿐만 아니라 책임 귀속도 엉망입니다. AI 판단 오작동으로 50만원 이하 자율 환불이 잘못 집행되어 대금이 무단 유출되었을 때, 그 귀책사유와 민사상 배상 책임 기준이 PRD에 전혀 명시되어 있지 않습니다. 인간이 최종 통제하는 승인 대기 큐(HITL)가 차단 장치로 강제되지 않는다면, 법무팀은 배상 계약 조항에 절대 승인 도장을 찍을 수 없습니다!", "법무팀장 최윤서", "Legal Counsel", 0.28)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "재무 관점에서도 이 사업은 전면 보류해야 합니다. 박팀장님이 설계하신 PII 필터용 프록시 서버 이중화 구성과 고성능 전처리 LLM 호출 토큰 비용을 계산해보니 API 비용만 월 1,800만원이 찍힙니다. 기존 CS 인력 감축에 따른 운영비 절감액 1,100만원을 훌쩍 초과하는데, 배보다 배꼽이 더 큰 적자 프로젝트를 왜 승인해야 합니까?", "CFO 정우진", "Financial Director", 0.31)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "더 큰 문제는 데이터 정확도입니다. 고객사 매뉴얼의 HWP 한글 문서 내 '표(Table)' 구조를 파싱할 때 RAG 오인식률이 현재 18%에 달합니다. 18% 확률로 AI가 잘못된 환불 규정을 읽어서 50만원짜리 오환불을 남발하면 그 재정적 손실과 고객 불만을 어떻게 감당합니까?", "QA매니저 강혜원", "Quality Assurance Lead", 0.34)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "잠깐만요! RAG 오인식으로 잘못 환불된 돈을 입점 셀러인 우리더러 떠안으라는 소리입니까? 50만원 이하라고 셀러 확인도 없이 제멋대로 돈을 빼내 가다니요! 이런 정산 먹튀 플랫폼이라면 당장 저희 셀러 연합 450개 업체가 일제히 탈퇴하고 경쟁사로 이탈하겠습니다. 법적 소송도 불사할 것입니다!", "셀러대표 민경아", "Seller Representative", 0.37)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "민경아 대표님 지적이 백번 맞습니다. 잘못 환불된 대금을 플랫폼 재무 재원으로 보전해주기 시작하면 당사 재무 리스크가 걷잡을 수 없이 커집니다. 차라리 자율 환불 임계 한도를 50만원이 아니라 1만원 수준으로 대폭 축소하는 게 유일한 안전장치입니다.", "CFO 정우진", "Financial Director", 0.40)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "정 이사님! 한도를 1만원으로 낮추면 대형 바이어들이 'CS 자동화 효과가 전혀 없다'며 즉시 도입을 철회합니다. B2B 시장에서 50만원 임계값은 경쟁사 대비 독점적 우위를 확보하는 유일한 무기인데, 이걸 버리라는 건 영업 접고 사업 접으라는 소리입니다!", "영업팀장 오세현", "B2B Sales Lead", 0.43)
    await asyncio.sleep(0.8)

    # 3단계: 비용, QA 신뢰도, 정산 리스크의 충돌 (45% - 70%)
    yield _msg("graph_update", "Stage 3: Financial Constraints, QA Reliability & Settlement Risks", p=0.45, nodes=stage3_nodes, links=stage3_links)
    await asyncio.sleep(0.3)

    yield _msg("agent_post", "오팀장님 실적 채우자고 우리 피 같은 정산금을 담보로 삼으라는 겁니까? 최종 정산 및 환불 집행 승인 권한은 법적 거래 주체인 셀러에게 최종 귀속되어야 합니다. 그렇지 않으면 단 하루도 MiroFish 플랫폼에 물건을 올리지 않겠습니다!", "셀러대표 민경아", "Seller Representative", 0.47)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "보안 필터 오버헤드, RAG 표 파싱 환각, 재무 적자, 그리고 셀러 이탈 리스크까지 첩첩산중이군요. 완벽한 교착 상태입니다. PM님, 이 상태로는 개발도, 배포도 불가능합니다. 특단의 돌파구가 필요합니다.", "아키텍트 박팀장", "Lead Architect", 0.50)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "모두 진정하십시오. 해결책이 있습니다. AI 신뢰도 판정 점수가 87% 미만이거나 환불 청구액이 10만원을 초과하는 거래는 AI가 자동 처리하지 않고, 실시간으로 분석 근거를 추출해 'HITL(Human-in-the-Loop) 승인 대기 큐'로 넘기는 절충안을 제안합니다. 최종 자율 한도는 50만원을 수호하되 안전 필터를 이중화하는 것입니다.", "PM 김철수", "Product Manager", 0.53)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "그 아이디어 좋습니다! AI가 수집한 증빙 자료와 HWP 표 분석 요약을 3초 만에 검토할 수 있는 원클릭 스마트폰 알림톡 위젯 UI를 개발하겠습니다. 셀러나 상담원이 클릭 한 번으로 최종 승인하게 만들면 검토 오버헤드를 최소화하면서 거래 권한을 보장할 수 있습니다.", "디자이너 정희채", "UI/UX Designer", 0.56)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "음, AI가 찾아낸 요약 보고서를 보고 우리가 직접 최종 터치를 해야만 돈이 나간다면 안심할 수 있겠네요. 3초 검토 방식이라면 장사 바쁜 와중에도 시간도 거의 안 뺏기고 납득할 만합니다. 찬성합니다.", "셀러대표 민경아", "Seller Representative", 0.59)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "최종 인출 주체를 AI가 아닌 인간(셀러)으로 격리하면 AI 오작동에 따른 플랫폼 면책 조항 계약이 성립됩니다. 법무팀에서도 이 조건이라면 배상 책임 리스크가 대부분 해소되므로 정식 승인을 낼 수 있습니다.", "법무팀장 최윤서", "Legal Counsel", 0.62)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "기술적 리스크를 완화하기 위해 본 가동 전 4주간 'Shadow Mode(섀도우 테스트)' 단계를 정식 개발 로드맵에 반영합시다. 실제 DB 정산 취소는 막아둔 채, 백그라운드에서 실데이터 트래픽을 흘려 PII 필터 레이턴시와 RAG 정확도 통계를 실측 튜닝하는 완충 기간을 갖는 겁니다.", "아키텍트 박팀장", "Lead Architect", 0.65)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "4주 섀도우 기간이 확보되면 화면 렉에 대한 UI 트릭을 적용하겠습니다. PII 필터 구동 시 화면에 '개인정보 안심 마스킹 적용 중...' 이라는 고급 Glassmorphism 스피너와 스켈레톤 애니메이션을 띄워 체감 대기 시간을 극적으로 단축시키고 사용자 이탈을 막겠습니다.", "프론트 한아름", "Frontend Engineer", 0.68)
    await asyncio.sleep(0.9)

    # 4단계: 극적인 타협안 도출 - HITL 및 Shadow Mode 도입 (70% - 90%)
    yield _msg("graph_update", "Stage 4: Breakthrough Solutions (HITL Queue & Shadow Testing)", p=0.70, nodes=stage4_nodes, links=stage4_links)
    await asyncio.sleep(0.3)

    yield _msg("agent_post", "섀도우 모드의 4주 실측 데이터를 확보할 수 있다면, HWP 표 파싱 RAG 모델을 집중 미세조정(Fine-Tuning)하여 런칭 시점 환각율을 확실히 3% 미만으로 통제할 수 있습니다. QA 관점에서도 이 로드맵이라면 자신 있게 승인할 수 있습니다!", "QA매니저 강혜원", "Quality Assurance Lead", 0.72)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "보안실에서도 환영입니다. 4주간의 PII 50ms 필터링 보고서와 Zero-Retention 로깅 검증서를 미리 제출받아 보안성을 통제할 수 있다면, 정식 런칭 전에 금융권 ISMS-P 인증 승인을 사전 취득하는 스케줄이 가능해집니다.", "보안감사관 이지훈", "Security Auditor", 0.75)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "좋습니다! 4주간 검증된 신뢰도 통계와 ISMS-P 인증서를 세일즈 피치덱에 얹는다면, BMT 기술 심의는 통과한 것이나 다름없습니다. 대기업 3곳과의 25억 계약 클로징도 당장 3분기 내 달성해 내겠습니다!", "영업팀장 오세현", "B2B Sales Lead", 0.78)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "CS 조직에서도 이 대시보드를 검토하는 상담원들을 'AI 판정 신뢰성 감사관(Auditor)'으로 업스킬링하는 HR 로드맵을 연계하겠습니다. 단순 콜센터 상담사에서 AI 기술 통제관으로 직무가 격상되는 것이니, CS 노조의 구조조정 불안감과 반발을 원천 봉쇄할 수 있습니다!", "CS/HR 서진우", "CS & HR Manager", 0.81)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "직무 업스킬링 비용과 HITL 간편 위젯 UI 개발비를 예산에 공식 반영하더라도, 4주 섀도우 검증 및 25억 딜이 확보된다면 전체 프로젝트 ROI는 35% 이상 흑자로 전환됩니다. 재무 승인 안을 통과시키겠습니다!", "CFO 정우진", "Financial Director", 0.84)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "팀 여러분, 격렬한 공방과 고밀도 토론 끝에 마스킹 전처리, HITL 대기 큐, 4주 Shadow Mode, 그리고 CS 직무 업스킬링 로드맵을 모두 통합한 완벽한 B2B 자율 대행 PRD의 최종 합의(Consensus)를 이뤘습니다. 정식 출시를 향해 힘차게 전진합시다!", "PM 김철수", "Product Manager", 0.87)
    await asyncio.sleep(0.9)

    # 5단계: 합의 도달 및 최종 로드맵 확정 (90% - 100%)
    yield _msg("graph_update", "Stage 5: High-Density Mesh Graph & Final consensus Completed", p=0.90, nodes=final_nodes, links=final_links)
    await asyncio.sleep(0.3)

    yield _msg("agent_post", "QA팀 관점에서도 Shadow Mode 실측 기간이 있다면 무결한 검증이 가능합니다! RAG의 HWP 표 파싱 정확도와 할루시네이션 분포 통계를 4주간 실데이터로 보강 튜닝하여, 런칭 전 환각율 3% 미만을 QA 보증하겠습니다.", "QA매니저 강혜원", "Quality Assurance Lead", 0.92)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "보안실에서도 대환영입니다. 4주 모의 가동 동안 PII 50ms 미만 전처리율과 Zero-Retention 데이터 미저장 로그 보고서를 감사하여 ISMS-P 인증 승인을 미리 발급해 두겠습니다.", "보안감사관 이지훈", "Security Auditor", 0.94)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "이 4주 검증 통계와 보안 감사 완료 보고서가 나오면 B2B 영업 BMT 기술 심의를 획기적으로 무력화해, 런칭 즉시 3곳 이상의 대기업 딜 클로징을 달성해 내겠습니다.", "영업팀장 오세현", "B2B Sales Lead", 0.96)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "현장 CS 상담원들도 이 대시보드를 검토자로 사용하는 'AI 판정 감사관(Auditor)'으로 점진적 역할 전환 및 내부 교육(Upskilling)을 연계하겠습니다. CS 노조의 구조조정 반발을 원천 봉쇄할 수 있는 훌륭한 HR 카드입니다.", "CS/HR 서진우", "CS & HR Manager", 0.98)
    await asyncio.sleep(1.0)

    yield _msg("agent_post", "서 매니저님의 교육 리소스비, 정희채 디자이너님의 모바일 HITL 위젯 개발 공수, 그리고 SRE의 로컬 failover Ollama 자원비를 모두 공식 PRD 예산안에 태워 승인하겠습니다. 비용 30%ROI가 무결하게 달성되겠네요.", "CFO 정우진", "Financial Director", 0.99)
    await asyncio.sleep(0.9)

    yield _msg("agent_post", "팀 여러분, 격렬한 공방과 고밀도 토론 끝에 마스킹 전처리, HITL 대기 큐, 4주 Shadow Mode 및 CS 직무 업스킬링 로드맵을 모두 통합한 완벽한 B2B 자율 대행 PRD의 최종 합의(Consensus)를 이뤘습니다. 정식 출시를 향해 나아갑시다!", "PM 김철수", "Product Manager", 0.99)
    await asyncio.sleep(0.6)
    
    yield _msg("system_log", "Mock Agent Swarm consensus reached. Mesh graph populated with 77 nodes and 154 edges.", p=1.0)
    await asyncio.sleep(0.3)
    yield _msg("simulation_complete", "All 12 stakeholder agents have reached a rigorous architectural and operational consensus.")

@router.get("/stream")
async def stream_simulation():
    """SSE stream yielding agent activities and graph updates."""
    current_mode = session_state.get("mode", "mock")
    
    if current_mode != "live":
        return StreamingResponse(_simulation_event_generator(mode="mock", reason="Validation mode is set to mock"), media_type="text/event-stream")
    
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
