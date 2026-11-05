"""
routes/simulation.py — Simulation proxy and SSE streaming endpoints.

Provides endpoints to bridge the PRD validation with the external MiroFish API Engine.
Features mocked asynchronous SSE streams for graph updates, agent chatter, and reporting, 
until full MiroFish wiring is established.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
from uuid import uuid4
from typing import Any, AsyncGenerator, Dict, Optional
from datetime import datetime, timezone

from app.config import settings
from app.services.llm_provider import get_llm_service
from app.services.mirofish_service import MiroFishService
from app.schemas import PRDDocument, Stakeholder

router = APIRouter(prefix="/simulation", tags=["simulation"])
logger = logging.getLogger("app.api.simulation")

from app.services.simulation_store import resolve_run, stream_events

mirofish = MiroFishService()


# Dense mock stakeholder panel shared by mock mode and live-LLM failure fallback.
MOCK_STAKEHOLDER_PANEL = [
                {
                    "name": "PM 김철수",
                    "role": "Product Manager",
                    "review_angle": "비즈니스 가치 극대화 및 기한 준수 평가\n- MVP 조기 런칭 가능성 및 시장성 분석\n- 개발 리소스 대비 사업성 ROI 검증",
                    "likely_objections": [
                        "핵심 가치와 무관한 오버엔지니어링으로 인한 출시 일정 지연 위험",
                        "자율 환불 범위 확대에 따른 재무적 리스크 및 손실 보증 미흡"
                    ]
                },
                {
                    "name": "부PM 이영희",
                    "role": "Associate PM",
                    "review_angle": "세부 요구사항 정의의 구체성 평가\n- 스토리보드 화면 구성의 정합성 검토\n- 현업 부서들과의 마일스톤 싱크 관리",
                    "likely_objections": [
                        "기획 명세의 모호성으로 인한 개발 일정 재산정 우려",
                        "유관 부서별 업무 범위 분쟁 조정 지연"
                    ]
                },
                {
                    "name": "개발 아키텍트 박팀장",
                    "role": "Lead Architect",
                    "review_angle": "시스템 확장성 및 아키텍처 타당성 검토\n- 표준 MCP(Model Context Protocol) 인터페이스 설계성\n- E2E Latency 1.5초 달성을 위한 분산 큐 구성",
                    "likely_objections": [
                        "비표준 레거시 연동으로 인한 기술 부채 누적 가능성",
                        "HWP 표 파싱의 한계에 따른 시스템 신뢰성 저하"
                    ]
                },
                {
                    "name": "시스템 아키텍트 임정민",
                    "role": "System Architect A",
                    "review_angle": "인프라 리소스 배치 및 로컬 Ollama 모델 가동 사양 분석\n- 분산 캐시 레이어 구성 최적화 검토\n- 고트래픽 대응 스케일아웃 시나리오 수립",
                    "likely_objections": [
                        "로컬 하드웨어 스펙 초과 시 스위칭 타임아웃 발생 위험",
                        "API Gateway 세션 유실로 인한 상태 비동화 현상"
                    ]
                },
                {
                    "name": "시스템 아키텍트 조경진",
                    "role": "System Architect B",
                    "review_angle": "데이터 파이프라인 이중화 검증\n- DB 트랜잭션 락 유발 지점 사전 분석\n- Failover 라우팅 지연 시간 300ms 준수 여부",
                    "likely_objections": [
                        "DB 쓰기 집중 시 커넥션 풀 고갈 및 세션 마비",
                        "대체 LLM 전환 성능 통계 부재"
                    ]
                },
                {
                    "name": "보안감사관 이지훈",
                    "role": "Security Auditor",
                    "review_angle": "PII 개인정보 비식별화 컴플라이언스 감독\n- Zero-Retention 데이터 미저장 정책 준수 증명\n- 금융 심의 및 ISMS-P 인증 승인 요건 검증",
                    "likely_objections": [
                        "외부 API 송수신 시 민감 로그 유출 및 해킹 침해 리스크",
                        "PII 마스킹 홉 우회 보안 누수 위험"
                    ]
                },
                {
                    "name": "보안엔지니어 정민우",
                    "role": "Security Engineer A",
                    "review_angle": "PII 마스킹 필터링 정규식 속도 검증\n- 네트워크 패킷 암호화 TLS 1.3 유효성 검사\n- 웹소켓 데이터 유실 감지 모니터링",
                    "likely_objections": [
                        "초당 1,000건 폭증 시 동기 필터 오버헤드 50ms 돌파 우려",
                        "인증 토큰 취약점에 따른 세션 탈취 리스크"
                    ]
                },
                {
                    "name": "보안엔지니어 강동호",
                    "role": "Security Engineer B",
                    "review_angle": "외부 공격 벡터 및 비정형 프롬프트 인젝션 취약점 검증\n- 가상 취약점 침투 테스트 수행\n- 로깅 감사 체계 무결성 확보 여부",
                    "likely_objections": [
                        "프롬프트 인젝션을 통한 내부 데이터베이스 우회 조회 리스크",
                        "감사 로그 보존 용량 초과 시 덮어쓰기 누수"
                    ]
                },
                {
                    "name": "법무팀장 최윤서",
                    "role": "Legal Counsel",
                    "review_angle": "AI 자율 환불의 법리적 책임 소재 분석\n- 상담원 개입(HITL) 의무 승인 정책 규정 해석\n- 오정산 피해 시 당사 배상 면책 한도 검토",
                    "likely_objections": [
                        "AI 오동작으로 인한 무단 대금 유출 시 구상권 청구 경로 미비",
                        "전자금융거래법 상 자율 제어 권한 위반 소지"
                    ]
                },
                {
                    "name": "법률대리인 신재현",
                    "role": "Legal Counsel B",
                    "review_angle": "약관 수정 조항 정합성 검사\n- B2B 판매 제약 계약서 내 AI 배상 한도 해석\n- 상담원 업스킬링 배치 시 노동법 위반 여부 검토",
                    "likely_objections": [
                        "판매자 연쇄 탈퇴 시 집단 소송 방어 조항 결여",
                        "상담원 직무 강제 전환 시 노동조합 단체 교섭 저항"
                    ]
                },
                {
                    "name": "CFO 정우진",
                    "role": "Financial Director",
                    "review_angle": "상담 운영 비용 절감 목표 대비 ROI 도출\n- 글로벌 LLM API 호출 토큰 비용 시뮬레이션\n- 서버 이중화 인프라 OPEX 적정성 평가",
                    "likely_objections": [
                        "PII 동기 필터 구동에 따른 API 토큰 낭비 및 재무적 적자 전환",
                        "TCR 성공형 수수료율 도입 시 현금 흐름 불확실성"
                    ]
                },
                {
                    "name": "재무팀원 송미경",
                    "role": "Financial Analyst",
                    "review_angle": "인프라 자본비용(CAPEX) 감가상각 분석\n- 월별 클라우드 서버 가동비 대비 매출 공헌도 분석\n- 섀도우 모드 4주 실측 비용 검증",
                    "likely_objections": [
                        "CS 운영비 절감액 대비 초기 솔루션 도입 감가상각비 초과 리스크",
                        "섀도우 모드 비용 예산 초과"
                    ]
                },
                {
                    "name": "QA매니저 강혜원",
                    "role": "Quality Assurance Lead",
                    "review_angle": "RAG 환각율 3% 미만 보증 체계 검증\n- 고객사 매뉴얼 HWP 표 문서 오인식률 계측\n- AI 판단 유예 시 이탈 큐 자동 전환 신뢰도 평가",
                    "likely_objections": [
                        "비정형 데이터 인식 한계로 인한 오답률 10% 돌파 위험",
                        "이탈 큐 이관 지연 시 대기 콜 폭증 대란"
                    ]
                },
                {
                    "name": "QA엔지니어 조현식",
                    "role": "QA Engineer A",
                    "review_angle": "엣지 케이스 시나리오 자동화 테스트 스크립트 작성\n- 신뢰성 분포 차트 시뮬레이터 가동 적합성 검토\n- 입력 데이터 유효성 경계값 검사",
                    "likely_objections": [
                        "RAG 응답 무작위성에 대한 동적 회귀 테스트 커버리지 누수",
                        "모의 트래픽 주입 시나리오 불충분"
                    ]
                },
                {
                    "name": "QA테스터 김태호",
                    "role": "QA Engineer B",
                    "review_angle": "모바일 알림톡 승인 버튼 및 터치 편의성 실기 테스트\n- 5만원 한도 강제 취소 시 수동 UI 응답 실측\n- 오류 팝업 발생 시 화면 복귀 상태 점검",
                    "likely_objections": [
                        "구형 안드로이드 브라우저 렌더링 깨짐 현상",
                        "다중 터치 시 중복 이벤트 API 다중 호출 버그"
                    ]
                },
                {
                    "name": "QA테스터 윤아름",
                    "role": "QA Engineer C",
                    "review_angle": "실시간 대시보드 갱신 이벤트 정밀 모니터링\n- 로그 검색 필터 키워드 정확도 검증\n- 툴팁 마우스 호버 바인딩 성능 수동 테스트",
                    "likely_objections": [
                        "대량 로그 적재 시 화면 지연 렉 발생",
                        "필터 키워드 불일치 시 텅 빈 화면 노출 현상"
                    ]
                },
                {
                    "name": "SRE리드 한상민",
                    "role": "SRE Lead",
                    "review_angle": "인프라 이중화 가용망 구축 및 SLA 99.9% 보증\n- 가동 시간 메트릭 측정 체계 구축\n- 장애 시 Ollama 로컬 전환 안정성 검증",
                    "likely_objections": [
                        "단일 LLM 장애 시 복원 로직 부재로 가용성 붕괴 우려",
                        "트래픽 서지 발생 시 컨테이너 오토스케일링 렉 유발"
                    ]
                },
                {
                    "name": "SRE엔지니어 윤석호",
                    "role": "SRE Engineer B",
                    "review_angle": "프로메테우스 연동 리소스 모니터링 대시보드 설계\n- CPU/Memory 임계치 알람 구성 타당성 검사\n- 로깅 스토리지 대역폭 검토",
                    "likely_objections": [
                        "디스크 IOPS 한계 도달 시 로그 누락 및 서버 다운",
                        "Failover 작동 스위칭 모니터링 실시간 연동 부재"
                    ]
                },
                {
                    "name": "디자이너 정희채",
                    "role": "UI/UX Designer A",
                    "review_angle": "HITL 승인 대시보드 와이어프레임 설계성 평가\n- 모바일 알림톡 승인 위젯 여정 가시성\n- 톤앤매너 설정의 드래그앤드롭 사용성 검증",
                    "likely_objections": [
                        "HITL 화면의 불필요한 단계 추가로 복잡성 가중 우려",
                        "정산 차트 시각 가독성 부실로 현업 피로도 상승"
                    ]
                },
                {
                    "name": "디자이너 박소율",
                    "role": "UI/UX Designer B",
                    "review_angle": "모던 글라스모피즘 스타일 가이드 라인 준수 검사\n- 접근성(A11y) 명암비 만족 여부 검토\n- 다크모드 대응 컬러 토큰 정합성 확인",
                    "likely_objections": [
                        "모바일 UI 대비 명암비 미달로 시인성 하락 리스크",
                        "일관되지 않은 보더 래디우스 설계"
                    ]
                },
                {
                    "name": "프론트엔드 한아름",
                    "role": "Frontend Engineer A",
                    "review_angle": "웹소켓 실시간 이벤트 수신 단 렌더링 최적화 검사\n- CPU 메인 스레드 렉 방지를 위한 가상 스크롤 검증\n- PII 안심 로더 글래스 애니메이션 성능 평가",
                    "likely_objections": [
                        "대량 실시간 차트 업데이트 시 프론트 브라우저 다운 현상",
                        "새로고침 연타 시 웹소켓 핸드셰이크 유실"
                    ]
                },
                {
                    "name": "프론트엔드 서지원",
                    "role": "Frontend Engineer B",
                    "review_angle": "리액트 컴포넌트 재사용 컴포넌트 설계 효율성\n- 로컬스토리지 토글 상태 바인딩 무결성 검증\n- 차트 라이브러리 메모리 누수 방지 조치 평가",
                    "likely_objections": [
                        "불필요한 전체 페이지 무한 렌더링 유발 가능성",
                        "컴포넌트 언마운트 시 메모리 누수 잔존"
                    ]
                },
                {
                    "name": "프론트엔드 김민식",
                    "role": "Frontend Engineer C",
                    "review_angle": "모바일 반응형 레이아웃 테스팅 및 디바이스 호환성 검증\n- 모바일 웹 크로스브라우징 체크\n- 터치 타겟 가독성 및 최소 48px 영역 사수 여부",
                    "likely_objections": [
                        "일부 구형 모바일 뷰포트에서 레이아웃 겹침 발생",
                        "아이폰 사파리 터치 지연 현상"
                    ]
                },
                {
                    "name": "백엔드 김도현",
                    "role": "Backend Engineer A",
                    "review_angle": "FastAPI ASGI 비동기 루프 성능 및 분산 락 최적화 검증\n- DB 커넥션 풀 가용 병목 파악\n- 50만원 환불 트랜잭션 동시성 격리 수준 검토",
                    "likely_objections": [
                        "동시 결제 취소 요청 시 데이터 정합성 깨짐 리스크",
                        "비동기 태스크 큐 브로커 연결 해제 장애"
                    ]
                },
                {
                    "name": "백엔드 임채원",
                    "role": "Backend Engineer B",
                    "review_angle": "벡터 데이터베이스 인덱스 효율성 및 표 전처리 검토\n- 표 파싱 RAG 오인식률 개선 임베딩 튜닝\n- PDF-to-Markdown 파서 변환 무결성 계측",
                    "likely_objections": [
                        "텍스트 파편화 RAG로 인한 컨텍스트 훼손 리스크",
                        "임베딩 청킹 크기 과다로 RAG 비용 상승"
                    ]
                },
                {
                    "name": "백엔드 오정훈",
                    "role": "Backend Engineer C",
                    "review_angle": "API Gateway 비동기 프록시 라우팅 무장애 동작 검증\n- 로깅 원천 정보 적재 속도 모니터링\n- Ollama 로컬 라우팅 오버헤드 300ms 사수 검사",
                    "likely_objections": [
                        "로컬 AI 스위칭 도중 메모리 가용량 오버플로우",
                        "로깅 가동 시 DB I/O 쓰기 지연"
                    ]
                },
                {
                    "name": "영업팀장 오세현",
                    "role": "B2B Sales Lead",
                    "review_angle": "B2B 엔터프라이즈 세일즈 계약 요구 사양 부합도 평가\n- 6월 기술 검증(BMT) 통과 마일스톤 준수 여부\n- 25억 규모 영업 파이프라인 개방 조건 분석",
                    "likely_objections": [
                        "자율 환불 한도를 낮출 경우 대기업 바이어의 CS 비용 감축 효용 저하로 이탈",
                        "경쟁 솔루션 대비 자동화 커버리지 격하"
                    ]
                },
                {
                    "name": "CS/HR 서진우",
                    "role": "CS & HR Manager",
                    "review_angle": "현업 CS 상담 조직의 심리적 저항 및 노사 갈등 중재 평가\n- 단순 반복 환불 업무 감축에 따른 교육 로드맵 타당성\n- AI 감사관 직무 업스킬링 체계 유효성 검사",
                    "likely_objections": [
                        "CS 운영 현장 노동조합의 일방적 구조조정 우려에 따른 파업 선언",
                        "업스킬링 리소스 및 교육비 예산 미비 시 반발"
                    ]
                },
                {
                    "name": "셀러대표 민경아",
                    "role": "Seller Representative A",
                    "review_angle": "50만원 자율 결제 취소 시 입점 셀러 정산 손실 차단성\n- 오정산 피해에 대한 플랫폼 귀책 및 배상 조항 평가\n- 모바일 검토 UI 내 증빙 요약 신뢰성 분석",
                    "likely_objections": [
                        "셀러 최종 확인 절차 누락에 따른 정산 오차 및 자금 유출 위험",
                        "오정산 대금 보상 제도 명문화 거부 시 집단 탈퇴 행동화"
                    ]
                },
                {
                    "name": "셀러대표 김동현",
                    "role": "Seller Representative B",
                    "review_angle": "정산 일자 지연 방지 및 이의 제기 프로세스 타당성 검사\n- 모바일 승인 알림톡 수신 속도 실시간성 평가\n- 셀러 정산 계좌 연동 안전성 분석",
                    "likely_objections": [
                        "알림톡 증빙 표 누락 또는 렌더 깨짐 시 승인 유예로 대금 동결 우려",
                        "플랫폼 신뢰 훼손 시 셀러 동맹 450개사의 즉시 이주"
                    ]
                }
            ]


MIN_STAKEHOLDER_COUNT = 8


def _live_llm_error_message(exc: Exception) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return (
            f"OpenAI {settings.openai_model} 응답이 {settings.llm_timeout}초 안에 완료되지 않았습니다. "
            "Mock 결과로 대체하지 않았습니다."
        )

    detail = str(exc).strip() or type(exc).__name__
    return f"OpenAI {settings.openai_model} 호출에 실패했습니다: {detail}"

@router.post("/propose-stakeholders")
async def propose_stakeholders(request: Request):
    """Analyze PRD and propose a list of stakeholders with personas."""
    try:
        payload = await request.json()
        if payload is None:
            payload = {}
    except Exception:
        payload = {}

    is_live = payload.get("live") is True
    prd_payload = payload.get("prd") if isinstance(payload.get("prd"), dict) else payload

    # 만약 Mock 모드이거나 Qwen 라이브 모드가 아닌 경우, 30인의 고밀도 전문가 명단 즉시 반환
    # 역할은 같아도 사람명이 달라지며 (ex. 아키텍트 A, 아키텍트 B), Review Angle과 Likely Objections가 매우 디테일하게 작성됨.
    if not is_live:
        return {
            "status": "success",
            "stakeholders": MOCK_STAKEHOLDER_PANEL,
        }

    # Live Mode
    try:
        # Try to parse as full PRD first
        try:
            prd = PRDDocument(**prd_payload)
        except Exception:
            stakeholders = await asyncio.wait_for(
                mirofish.propose_stakeholders_from_dict(prd_payload),
                timeout=settings.llm_timeout,
            )
        else:
            stakeholders = await asyncio.wait_for(
                mirofish.propose_stakeholders(prd),
                timeout=settings.llm_timeout,
            )

        if len(stakeholders) < MIN_STAKEHOLDER_COUNT:
            logger.warning(
                "Stakeholder proposal returned %d personas in live mode",
                len(stakeholders),
            )
            return {
                "status": "error",
                "message": "Live LLM이 충분한 Reality Seeds를 생성하지 못했습니다. Mock 결과로 대체하지 않았습니다.",
            }

        return {"status": "success", "stakeholders": [s.model_dump() for s in stakeholders]}
    except Exception as e:
        logger.error("Live stakeholder proposal failed: %s", e)
        return {
            "status": "error",
            "message": _live_llm_error_message(e),
        }

@router.post("/setup")
async def setup_simulation(request: Request, *, session_state: dict[str, Any] = Depends(resolve_run)):
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
        session_state["status"] = "setup"
        
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
async def start_simulation(payload: dict[str, Any], *, session_state: dict[str, Any] = Depends(resolve_run)):
    """Start the multi-agent simulation run on MiroFish."""
    # 사용자가 Reality Seeds 설정창에서 조정한 stakeholder 리스트를 받아 세션 상태에 보관
    session_state["stakeholder_personas"] = payload.get("stakeholder_personas", [])
    
    is_live = payload.get("live", False)
    session_state["mode"] = "live" if is_live else "mock"

    if is_live and settings.mirofish_mode != "live":
        raise HTTPException(409, "Live engine mode is disabled")

    if not is_live:
        return {"status": "started", "simulation_id": session_state["run_id"]}

    try:
        project_id = payload.get("project_id") or session_state.get("project_id")
        graph_id = payload.get("graph_id") or session_state.get("graph_id")
        
        if not project_id or not graph_id:
             # Try to get from payload if not in session
             project_id = payload.get("project_id")
             graph_id = payload.get("graph_id")
             
        if not project_id:
             raise HTTPException(status_code=400, detail="No project_id found. Call /setup first.")

        sim_id = await mirofish.create_and_start_simulation(project_id, graph_id)
        session_state["simulation_id"] = sim_id
        
        return {"status": "started", "simulation_id": session_state["run_id"], "engine_simulation_id": sim_id}
    except Exception as e:
        logger.error(f"Start failed: {e}")
        if isinstance(e, HTTPException):
            raise
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

def _simulation_context(*, session_state: dict[str, Any]) -> dict[str, Any]:
    prd = session_state.get("prd_snapshot") or {}
    product = prd.get("product") or {}
    problem = prd.get("problem") or {}
    solution = prd.get("solution") or {}
    requirements = (prd.get("requirements") or {}).get("functional") or []
    requirement_texts = [
        str(item.get("description") or item.get("title") or item.get("id"))
        for item in requirements
        if isinstance(item, dict)
    ]
    return {
        "product_name": str(product.get("name") or product.get("one_liner") or "현재 제품"),
        "problem": str(problem.get("core_problem") or problem.get("summary") or "해결하려는 문제"),
        "solution": str(solution.get("summary") or solution.get("value_proposition") or "제안된 해결 방식"),
        "requirements": [item for item in requirement_texts if item],
    }


def _build_mock_dialogues(personas: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = context["requirements"] or ["MVP 범위와 인수 기준"]
    dialogues: list[dict[str, Any]] = []
    active_personas = personas[:10]
    for index, persona in enumerate(active_personas):
        name = str(persona.get("name") or f"Stakeholder {index + 1}")
        role = str(persona.get("role") or "Stakeholder")
        review_angle = str(persona.get("review_angle") or "현재 PRD의 실행 가능성")
        objections = persona.get("likely_objections") or []
        objection = str(objections[0]) if objections else "명확한 인수 기준이 필요합니다."
        requirement = requirements[index % len(requirements)]
        content = (
            f"{context['product_name']}의 '{context['problem']}' 가설을 {review_angle} 관점에서 검토했습니다. "
            f"우선 '{requirement}' 요구사항이 이 문제를 검증할 수 있도록 범위와 측정 기준을 명확히 해야 합니다. "
            f"주요 이의는 '{objection}'입니다."
        )
        dialogues.append({
            "speaker": name,
            "role": role,
            "reply_to": "topic",
            "round": 1,
            "stance": "challenge",
            "claim_reference": "현재 제품 가설과 요구사항",
            "content": content,
        })

    for index, persona in enumerate(active_personas):
        name = str(persona.get("name") or f"Stakeholder {index + 1}")
        role = str(persona.get("role") or "Stakeholder")
        previous_name = str(active_personas[index - 1].get("name") or "앞선 참여자")
        requirement = requirements[(index + 1) % len(requirements)]
        objections = persona.get("likely_objections") or []
        objection = str(objections[-1]) if objections else "검증 가능한 기준이 필요합니다."
        dialogues.append({
            "speaker": name,
            "role": role,
            "reply_to": previous_name,
            "round": 2,
            "stance": "challenge",
            "claim_reference": f"{previous_name}의 범위 및 검증 기준 우려",
            "content": (
                f"{previous_name}의 우려만으로 '{requirement}' 범위를 축소하는 데는 반대합니다. "
                f"'{objection}'을 확인할 실패 시나리오와 책임자를 같은 실험에 넣어야 하며, 그 결과가 나오기 전에는 다음 단계로 진행할 수 없습니다."
            ),
        })

    for index, persona in enumerate(active_personas):
        name = str(persona.get("name") or f"Stakeholder {index + 1}")
        role = str(persona.get("role") or "Stakeholder")
        previous_name = str(active_personas[index - 1].get("name") or "앞선 참여자")
        requirement = requirements[(index + 2) % len(requirements)]
        dialogues.append({
            "speaker": name,
            "role": role,
            "reply_to": previous_name,
            "round": 3,
            "stance": "compromise",
            "claim_reference": f"{previous_name}의 실패 시나리오와 책임자 요구",
            "content": (
                f"{previous_name}의 지적은 수용하되, '{requirement}'을 무기한 보류하면 고객 검증 자체가 불가능해집니다. "
                f"따라서 위험 조건에서는 사람 승인으로 전환하고, 재처리·취소·환불 상태를 함께 추적하는 제한된 파일럿으로 합의해야 합니다."
            ),
        })
    return dialogues


def _build_mock_risks(personas: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    requirements = context["requirements"] or ["MVP 범위와 인수 기준"]
    for index, persona in enumerate(personas[:3]):
        objections = persona.get("likely_objections") or []
        description = str(objections[0]) if objections else f"{requirements[index % len(requirements)]}의 검증 기준이 부족합니다."
        risks.append({
            "title": f"{persona.get('name', f'이해관계자 {index + 1}')}의 핵심 우려",
            "description": description,
            "related_requirement": requirements[index % len(requirements)],
            "raised_by": str(persona.get("name") or ""),
            "participants": [
                str(persona.get("name") or ""),
                str(personas[index - 1].get("name") or "") if personas else "",
            ],
            "emerges_after": (len(personas[:10]) * 2) + index + 1,
        })
    return risks


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract one JSON object from an LLM response without accepting prose."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        candidate = candidate.rsplit("```", 1)[0].strip()

    start = candidate.find("{")
    if start < 0:
        raise ValueError("Live LLM response did not contain a JSON object")
    decoded, _ = json.JSONDecoder().raw_decode(candidate[start:])
    if not isinstance(decoded, dict):
        raise ValueError("Live LLM response must be a JSON object")
    return decoded


async def _build_live_dialogues(
    personas: list[dict[str, Any]], context: dict[str, Any]
, *, session_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate a three-round debate where each round receives prior turns."""
    active_personas = personas[:10]
    persona_context = "\n".join(
        "- {name} ({role}): 관점={angle}; 예상 이의={objections}".format(
            name=persona.get("name", f"Stakeholder {index + 1}"),
            role=persona.get("role", "Stakeholder"),
            angle=persona.get("review_angle", "PRD 실행 가능성"),
            objections=" / ".join(persona.get("likely_objections") or ["명확한 인수 기준 필요"]),
        )
        for index, persona in enumerate(active_personas)
    )
    requirements = "\n".join(f"- {item}" for item in context["requirements"][:6]) or "- MVP 범위와 인수 기준"
    persona_by_name = {
        str(persona.get("name")): persona
        for persona in active_personas
        if persona.get("name")
    }

    def format_history(turns: list[dict[str, Any]]) -> str:
        return "\n".join(
            f"{index + 1}. {turn['speaker']} → {turn['reply_to']} [{turn['stance']}]: "
            f"{turn['content']} (인용 주장: {turn['claim_reference']})"
            for index, turn in enumerate(turns)
        )

    async def generate_round(round_number: int, history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        prior_discussion = format_history(history) or "아직 이전 발언이 없습니다."
        response_rule = (
            "각 참여자는 topic을 대상으로 자신의 검증 관점을 제기하고, claim_reference에는 현재 제품 가설 또는 요구사항을 구체적으로 적으세요."
            if round_number == 1
            else "각 참여자는 반드시 이전 토론의 다른 참여자 한 명을 `reply_to`로 지정하고, 그 사람의 실제 주장 한 가지를 `claim_reference`에 인용해 반박·수정·조건부 수용하세요. 독립 의견은 금지합니다."
        )
        risk_rule = (
            "Round 3에서만, 최소 두 참여자의 상충된 주장 때문에 새롭게 확인된 리스크를 3~6개 도출하세요."
            if round_number == 3
            else "risks는 빈 배열로 반환하세요."
        )
        prompt = f"""
당신은 제품 검증 토론의 진행자입니다. 이번에는 Round {round_number}만 생성하세요.

제품: {context['product_name']}
문제: {context['problem']}
해결 가설: {context['solution']}
요구사항:
{requirements}

Reality Seeds:
{persona_context}

이전 토론 로그:
{prior_discussion}

규칙:
1. Reality Seed마다 정확히 한 발언을 생성합니다.
2. {response_rule}
3. `content`는 대상의 이름과 구체적 정책·수치·범위를 직접 언급하고, 반대 근거와 수정안을 모두 포함한 한국어 2~3문장이어야 합니다.
4. {risk_rule}

JSON만 반환하세요:
{{"dialogues":[{{"speaker":"Reality Seed의 정확한 이름","role":"역할","reply_to":"대상 이름 또는 topic","round":{round_number},"stance":"challenge|support|compromise","claim_reference":"상대의 구체적 주장 요약","content":"직접 반박 또는 보완 발언"}}],"risks":[{{"title":"토론 끝에 도출된 리스크","description":"상충 주장과 발생 조건","related_requirement":"관련 요구사항","raised_by":"제기자 이름","participants":["상충한 두 참여자 이름"]}}]}}
"""
        response = await get_llm_service().chat([
            {"role": "system", "content": "Return only valid JSON. Generate a grounded Korean multi-agent debate, not a list of independent opinions."},
            {"role": "user", "content": prompt},
        ])
        data = _extract_json_object(response)
        raw_dialogues = data.get("dialogues")
        if not isinstance(raw_dialogues, list):
            raise ValueError(f"Live LLM round {round_number} did not include dialogues")

        previous_speakers = {turn["speaker"] for turn in history}
        turns: list[dict[str, Any]] = []
        seen_speakers: set[str] = set()
        for item in raw_dialogues:
            if not isinstance(item, dict):
                continue
            speaker = str(item.get("speaker") or "").strip()
            if speaker not in persona_by_name or speaker in seen_speakers:
                continue
            reply_to = str(item.get("reply_to") or "").strip()
            if round_number == 1:
                reply_to = "topic"
            elif reply_to not in previous_speakers or reply_to == speaker:
                continue
            claim_reference = str(item.get("claim_reference") or "").strip()
            content = str(item.get("content") or "").strip()
            stance = str(item.get("stance") or "").strip()
            if not claim_reference or not content or stance not in {"challenge", "support", "compromise"}:
                continue
            turns.append({
                "speaker": speaker,
                "role": str(item.get("role") or persona_by_name[speaker].get("role") or "Stakeholder"),
                "reply_to": reply_to,
                "round": round_number,
                "stance": stance,
                "claim_reference": claim_reference,
                "content": content,
            })
            seen_speakers.add(speaker)

        if set(persona_by_name) != seen_speakers:
            raise ValueError(f"Live LLM round {round_number} did not produce one valid reply for every Reality Seed")
        raw_risks = data.get("risks")
        return turns, raw_risks if isinstance(raw_risks, list) else []

    dialogues: list[dict[str, Any]] = []
    raw_risks: list[dict[str, Any]] = []
    for round_number in range(1, 4):
        turns, round_risks = await generate_round(round_number, dialogues)
        dialogues.extend(turns)
        if round_number == 3:
            raw_risks = round_risks

    risks = []
    for index, item in enumerate(raw_risks[:6]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        raised_by = str(item.get("raised_by") or "").strip()
        participants = [name for name in item.get("participants", []) if name in persona_by_name] if isinstance(item.get("participants"), list) else []
        if not title or not description or len(participants) < 2:
            continue
        risks.append({
            "title": title,
            "description": description,
            "related_requirement": str(item.get("related_requirement") or "").strip(),
            "raised_by": raised_by if raised_by in persona_by_name else participants[0],
            "participants": participants,
            "emerges_after": len(dialogues) - len(active_personas) + index + 1,
        })
    if not risks:
        raise ValueError("Live LLM did not derive risks from the final debate round")
    session_state["derived_risks"] = risks
    return dialogues


def _build_mock_report(*, session_state: dict[str, Any]) -> str:
    context = _simulation_context(session_state=session_state)
    events = session_state.get("simulation_events") or []
    posts = [event for event in events if event.get("type") == "agent_post"]
    run_id = session_state.get("simulation_run_id", "unknown")
    mode = session_state.get("last_simulation_mode", "mock")
    if not posts:
        return "# MiroFish 시뮬레이션 검증 보고서\n\n이번 실행에서 수집된 토론 이벤트가 없습니다. 시뮬레이션을 다시 실행한 뒤 보고서를 생성해주세요."

    findings = "\n".join(
        f"- **{post.get('agent_name', 'Stakeholder')} ({post.get('agent_type', 'Unknown')})**: {post.get('content', '')}"
        for post in posts
    )
    requirements = context["requirements"] or ["MVP 범위와 인수 기준"]
    actions = "\n".join(f"- {item}" for item in requirements[:5])
    return (
        f"# MiroFish 시뮬레이션 검증 보고서\n\n"
        f"- **실행 ID:** `{run_id}`\n- **실행 모드:** `{mode}`\n- **제품:** {context['product_name']}\n"
        f"- **수집된 토론 이벤트:** {len(posts)}건\n\n"
        f"## 검증한 문제와 해결 가설\n- 문제: {context['problem']}\n- 해결 가설: {context['solution']}\n\n"
        f"## 이번 실행의 이해관계자 발언 근거\n{findings}\n\n"
        f"## 다음 검증 우선순위\n{actions}\n\n"
        f"## 판정\n이 보고서는 위 실행 ID에서 수집한 {len(posts)}건의 토론 이벤트를 바탕으로 생성되었습니다. "
        f"`mock` 또는 `live_fallback` 모드라면 실제 MiroFish 엔진 호출 결과가 아닌 현재 PRD와 Reality Seeds를 입력으로 한 로컬 시뮬레이션입니다."
    )


async def _build_live_report(*, session_state: dict[str, Any]) -> str:
    """Generate a report from the dialogue stored for the current live LLM run."""
    context = _simulation_context(session_state=session_state)
    posts = [event for event in session_state.get("simulation_events", []) if event.get("type") == "agent_post"]
    if not posts:
        raise ValueError("No live simulation dialogue was recorded")
    discussion = "\n".join(
        f"- Round {post.get('round', '?')} | {post.get('agent_name', 'Stakeholder')} → "
        f"{post.get('reply_to', 'topic')} [{post.get('stance', 'statement')}]: "
        f"{post.get('content', '')} (인용: {post.get('claim_reference', '없음')})"
        for post in posts
    )
    prompt = f"""
아래는 한 번의 Live LLM 시뮬레이션에서 생성된 실제 토론 로그입니다. 이 로그만 근거로 한국어 Markdown 검증 보고서를 작성하세요.

실행 ID: {session_state.get('simulation_run_id', 'unknown')}
제품: {context['product_name']}
문제: {context['problem']}
해결 가설: {context['solution']}
토론 로그:
{discussion}

반드시 다음 섹션을 포함하세요: 핵심 합의, 주요 리스크, 요구사항 보완, 다음 검증 우선순위. 로그에 없는 사실은 단정하지 마세요.
"""
    return await get_llm_service().chat([
        {"role": "system", "content": "You write concise Korean Markdown product validation reports grounded only in supplied evidence."},
        {"role": "user", "content": prompt},
    ])
async def _simulation_event_generator(
    mode: str = "mock",
    reason: str | None = None,
    dialogues: list[dict[str, Any]] | None = None,
 *, session_state: dict[str, Any]) -> AsyncGenerator[str, None]:
    """Rich SSE stream for simulation with 30+ dynamic stakeholder personas and real-time graph growth sync."""
    import json
    import asyncio
    from datetime import datetime, timezone

    run_id = session_state["run_id"]
    session_state["simulation_run_id"] = run_id
    session_state["simulation_events"] = []
    session_state["last_simulation_mode"] = mode
    session_state["last_simulation_reason"] = reason

    def emit(event: dict[str, Any]) -> str:
        event["run_id"] = run_id
        event["mode"] = mode
        event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        session_state["simulation_events"].append(event)
        return f"data: {json.dumps(event)}\n\n"

    raw_personas = session_state.get("stakeholder_personas") or MOCK_STAKEHOLDER_PANEL
    context = _simulation_context(session_state=session_state)
    dialogues = dialogues or _build_mock_dialogues(raw_personas, context)
    risk_items = session_state.get("derived_risks") or _build_mock_risks(raw_personas, context)
    stakeholder_nodes: list[dict[str, Any]] = []
    stakeholder_ids: dict[str, str] = {}
    for dialogue in dialogues:
        name = str(dialogue["speaker"])
        role = str(dialogue["role"])
        if name in stakeholder_ids:
            continue
        node_id = f"stakeholder-{len(stakeholder_nodes)}"
        stakeholder_ids[name] = node_id
        stakeholder_nodes.append({
            "id": node_id,
            "group": len(stakeholder_nodes) % 4,
            "label": name,
            "role": role,
            "summary": f"{role} 관점의 Reality Seed 참여자",
            "goal": "다른 참여자와 쟁점을 검증하고 실행 가능한 합의를 도출합니다.",
        })
    product_node = {
        "id": "topic",
        "group": 6,
        "label": context["product_name"],
        "role": "시뮬레이션 주제",
        "summary": context["problem"],
        "goal": "참여자 토론을 통해 핵심 가설과 리스크를 검증합니다.",
    }
    risk_nodes = [
        {
            "id": f"risk-{index}",
            "group": 4,
            "label": str(risk["title"]),
            "role": "새롭게 도출된 리스크",
            "summary": str(risk["description"]),
            "goal": f"{risk.get('related_requirement') or '관련 요구사항'}의 보완과 검증",
        }
        for index, risk in enumerate(risk_items)
    ]
    connection_counts: dict[tuple[str, str], int] = {}
    visible_risk_ids: set[str] = set()

    def add_connection(first_id: str, second_id: str) -> None:
        key = tuple(sorted((first_id, second_id)))
        connection_counts[key] = connection_counts.get(key, 0) + 1

    def graph_snapshot() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        visible_nodes = stakeholder_nodes + [product_node] + [
            node for node in risk_nodes if node["id"] in visible_risk_ids
        ]
        return visible_nodes, [
            {
                "source": source,
                "target": target,
                "weight": count,
                "label": f"{count}회 토론",
            }
            for (source, target), count in connection_counts.items()
        ]

    yield emit({"type": "mode_check", "reason": reason})
    initial_nodes, initial_links = graph_snapshot()
    yield emit({
        "type": "system_log",
        "content": f"{mode} simulation started for {context['product_name']}. Run ID: {run_id}",
        "nodes": initial_nodes,
        "links": initial_links,
        "progress": 0.02,
    })
    for index, dialogue in enumerate(dialogues, start=1):
        name = str(dialogue["speaker"])
        role = str(dialogue["role"])
        content = str(dialogue["content"])
        speaker_id = stakeholder_ids[name]
        reply_to = str(dialogue.get("reply_to") or "topic")
        reply_id = stakeholder_ids.get(reply_to, "topic")
        add_connection(reply_id, speaker_id)
        for risk_index, risk in enumerate(risk_items):
            if int(risk.get("emerges_after") or len(dialogues) + 1) != index:
                continue
            risk_id = risk_nodes[risk_index]["id"]
            visible_risk_ids.add(risk_id)
            participants = risk.get("participants") or [risk.get("raised_by")]
            connected_participant = False
            if isinstance(participants, list):
                for participant in participants:
                    participant_id = stakeholder_ids.get(str(participant))
                    if participant_id:
                        add_connection(participant_id, risk_id)
                        connected_participant = True
            if not connected_participant:
                add_connection(speaker_id, risk_id)
            add_connection(risk_id, "topic")
        visible_nodes, visible_links = graph_snapshot()
        yield emit({
            "type": "agent_post",
            "agent_name": name,
            "agent_type": role,
            "content": content,
            "reply_to": reply_to,
            "round": dialogue.get("round"),
            "stance": dialogue.get("stance"),
            "claim_reference": dialogue.get("claim_reference"),
            "nodes": visible_nodes,
            "links": visible_links,
            "progress": 0.05 + (0.9 * index / len(dialogues)),
        })
        await asyncio.sleep(0.55)
    final_nodes, final_links = graph_snapshot()
    yield emit({"type": "simulation_complete", "content": "Simulation completed.", "nodes": final_nodes, "links": final_links, "progress": 1.0})
    return


async def _live_llm_event_generator(reason: str | None = None, *, session_state: dict[str, Any]) -> AsyncGenerator[str, None]:
    """Run the current PRD through the configured LLM when no MiroFish engine is reachable."""
    context = _simulation_context(session_state=session_state)
    personas = session_state.get("stakeholder_personas") or []
    try:
        dialogues = await _build_live_dialogues(personas, context, session_state=session_state)
    except Exception as exc:
        session_state["mode"] = "live_error"
        payload = {
            "type": "simulation_error",
            "mode": "live_error",
            "reason": f"Live LLM simulation failed: {exc}",
            "content": "Live ON 상태에서 Mock 결과로 대체하지 않았습니다. API 키, 모델, 사용 한도를 확인한 뒤 다시 시도해주세요.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield f"data: {json.dumps(payload)}\n\n"
        return

    session_state["mode"] = "live_llm"
    async for event in _simulation_event_generator(
        mode="live_llm",
        reason=reason or "Configured LLM generated this simulation because the MiroFish engine is unavailable.",
        dialogues=dialogues,
     session_state=session_state):
        yield event


@router.get("/stream")
async def stream_simulation(*, session_state: dict[str, Any] = Depends(resolve_run)):
    """SSE stream yielding agent activities and graph updates."""
    current_mode = session_state.get("mode", "mock")
    
    if current_mode == "live_llm":
        return stream_events(_live_llm_event_generator(session_state=session_state), run=session_state)

    if current_mode == "live_error":
        return stream_events(
            _live_llm_event_generator("The previous live run failed; retrying the configured LLM.", session_state=session_state),
            run=session_state,
        )

    if current_mode != "live":
        return stream_events(_simulation_event_generator(mode="mock", reason="Validation mode is set to mock", session_state=session_state), run=session_state)
    
    sim_id = session_state.get("simulation_id")
    if not sim_id:
        return stream_events(
            _live_llm_event_generator("MiroFish simulation session was not created; using the configured Live LLM.", session_state=session_state),
            run=session_state,
        )

    # Live Mode Connection check and Polling with Graceful Fallback
    import httpx
    try:
        # Check connection to MiroFish API engine first
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.mirofish_base_url}/health")
            resp.raise_for_status()
    except Exception as ec:
        logger.warning("MiroFish Engine is unreachable (%s). Switching to configured Live LLM.", ec)
        session_state["mode"] = "live_llm"
        return stream_events(
            _live_llm_event_generator(f"MiroFish engine unreachable: {ec}. Using the configured Live LLM.", session_state=session_state),
            run=session_state,
        )

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
                node_ids: set[str] = set()
                
                label_to_group = {
                    "agent": 0,
                    "stakeholder": 0,
                    "risk": 4,
                    "solution": 5,
                    "alternative": 5,
                    "requirement": 5,
                    "fact": 6
                }
                
                for nd in raw_graph.get("nodes", []):
                    node_id = nd.get("uuid") or nd.get("name")
                    if not node_id:
                        continue

                    node_id = str(node_id)
                    node_ids.add(node_id)
                    node_label = str(nd.get("name") or node_id)
                    
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
                    if source is not None and target is not None:
                        source = str(source)
                        target = str(target)
                    if source in node_ids and target in node_ids:
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
            logger.error("Error during MiroFish live event polling: %s. Switching to configured Live LLM.", e)
            session_state["mode"] = "live_llm"
            yield f'data: {json.dumps({"type": "mode_check", "mode": "live_llm", "reason": f"MiroFish event polling failed: {e}. Using the configured Live LLM."})}\n\n'
            async for live_event in _live_llm_event_generator(f"MiroFish event polling failed: {e}. Using the configured Live LLM.", session_state=session_state):
                yield live_event

    return stream_events(_mirofish_event_generator(), run=session_state)


@router.get("/{sim_id}/result")
async def get_simulation_result(sim_id: str, session_state: dict = Depends(resolve_run)):
    """Fetch completed simulation dialogue logs."""
    return {"sim_id": session_state["run_id"], "status": session_state["status"], "logs": session_state.get("simulation_events", []), "report_markdown": session_state.get("report_markdown")}

@router.post("/{sim_id}/report")
async def generate_report(sim_id: str, retry: bool = False, *, session_state: dict[str, Any] = Depends(resolve_run)):
    """Trigger the ReportAgent to generate a Markdown report."""
    if session_state.get("report_status") == "streaming":
        raise HTTPException(409, "Report stream already running")
    if retry:
        for key in ("report_task_id", "report_id", "report_status", "report_events", "report_markdown"):
            session_state.pop(key, None)
    if session_state.get("mode") == "live_llm":
        return {"status": "generating", "task_id": "live_llm_report"}

    if session_state.get("mode") != "live":
        session_state["report_task_id"] = "mock_task_123"
        return {"status": "generating", "task_id": "mock_task_123"}
        
    try:
        resp = await mirofish.generate_report(session_state["simulation_id"], force_regenerate=retry)
        session_state["report_id"] = resp.get("data", {}).get("report_id")
        task_id = resp.get("data", {}).get("task_id", "")
        session_state["report_task_id"] = task_id
        return {"status": "generating", "task_id": task_id}
    except Exception as e:
        logger.error("Failed to trigger live MiroFish report: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

async def _report_event_generator(*, session_state: dict[str, Any]):
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

    markdown = _build_mock_report(session_state=session_state)
    yield _msg({"type": "report_complete", "markdown": markdown})


async def _live_llm_report_event_generator(*, session_state: dict[str, Any]) -> AsyncGenerator[str, None]:
    """Generate the report with the configured LLM from this run's stored dialogue."""
    def _msg(data: dict[str, Any]) -> str:
        data["mode"] = "live_llm"
        return f"data: {json.dumps(data)}\n\n"

    yield _msg({"type": "planning", "title": "토론 로그 분석 중"})
    try:
        markdown = await _build_live_report(session_state=session_state)
    except Exception as exc:
        logger.error("Live LLM report generation failed: %s", exc)
        yield _msg({
            "type": "report_error",
            "markdown": (
                "# Live 보고서 생성 실패\n\n"
                "Mock 보고서로 대체하지 않았습니다. API 키, 모델, 사용 한도를 확인한 뒤 다시 시도해주세요.\n\n"
                f"오류: `{exc}`"
            ),
        })
        return

    yield _msg({"type": "section_start", "section_id": 1, "title": "토론 근거 정리"})
    yield _msg({"type": "section_complete", "section_id": 1})
    yield _msg({"type": "report_complete", "markdown": markdown})

@router.get("/{sim_id}/report/stream")
async def stream_report(sim_id: str, *, session_state: dict[str, Any] = Depends(resolve_run)):
    """SSE stream yielding report generation progress and final markdown."""
    if session_state.get("mode") == "live_llm":
        return stream_events(_live_llm_report_event_generator(session_state=session_state), run=session_state, report=True)

    if session_state.get("mode") != "live":
        return stream_events(_report_event_generator(session_state=session_state), run=session_state, report=True)

    sim_id = session_state.get("simulation_id") or session_state["run_id"]
        
    task_id = session_state.get("report_task_id")
    
    # Auto-trigger report if task_id not initialized
    if not task_id and not session_state.get("report_id"):
        try:
            resp = await mirofish.generate_report(session_state["simulation_id"])
            session_state["report_id"] = resp.get("data", {}).get("report_id")
            task_id = resp.get("data", {}).get("task_id", "")
            session_state["report_task_id"] = task_id
        except Exception as e:
            logger.error("Failed to auto-trigger live MiroFish report generation: %s", e)
            error_message = str(e)

            async def _live_engine_report_error(message: str = error_message) -> AsyncGenerator[str, None]:
                payload = {
                    "type": "report_error",
                    "mode": "live_error",
                    "markdown": (
                        "# Live MiroFish 보고서 생성 실패\n\n"
                        "Mock 보고서로 대체하지 않았습니다. MiroFish 엔진 연결과 API 설정을 확인한 뒤 다시 시도해주세요.\n\n"
                        f"오류: `{message}`"
                    ),
                }
                yield f"data: {json.dumps(payload)}\n\n"

            return stream_events(_live_engine_report_error(), run=session_state, report=True)

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
                status_resp = await mirofish.get_report_status(task_id=task_id) if task_id else {"data": {"status": "completed"}}
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

                if status == "completed":
                    # Complete all remaining active sections
                    for sec in list(active_sections.keys()):
                        if active_sections[sec] == "running":
                            yield f'data: {json.dumps({"type": "section_complete", "section_id": sec})}\n\n'
                            active_sections[sec] = "complete"
                            
                    # Fetch finalized report content
                    report_id = task_data.get("result", {}).get("report_id") or session_state.get("report_id")
                    if not report_id:
                        raise ValueError("Completed task did not identify its report")
                    report_resp = await mirofish.get_report(report_id)
                    report_data = report_resp.get("data", {})
                    markdown_content = report_data.get("markdown_content")
                    if not markdown_content:
                        raise ValueError("Completed report has no content")
                    
                    yield f'data: {json.dumps({"type": "report_complete", "markdown": markdown_content})}\n\n'
                    break
                    
                elif status == "failed":
                    error_msg = task_data.get("error", "Generation failed")
                    err_md = f"## ⚠️ Report Generation Failed\n\n{error_msg}"
                    yield f'data: {json.dumps({"type": "report_error", "markdown": err_md})}\n\n'
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
            yield f'data: {json.dumps({"type": "report_error", "markdown": "## ⚠️ Report Generation Timed Out"})}\n\n'

    return stream_events(_mirofish_report_event_generator(), run=session_state, report=True)


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

    # 1.5. Render and inject markdown into prd artifacts for instant UI preview
    from app.services.markdown_renderer import render_prd_markdown
    rich_prd["artifacts"] = {
        "prd_markdown": render_prd_markdown(rich_prd)
    }

    # 2. Save complete state directly to session store
    state = session_store.get_session(body.session_id)
    if state is None:
        state = SessionState(session_id=body.session_id)
    
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
