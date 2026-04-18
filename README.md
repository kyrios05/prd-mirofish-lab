# 🐟 PRD-MiroFish-Lab

> **대화를 통해 구조화된 PRD를 생성하고, MiroFish 시뮬레이션으로 검증하는 시스템**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-530%20passed-brightgreen)](https://github.com/kyrios05/prd-mirofish-lab)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 목차

- [프로젝트 소개](#-프로젝트-소개)
- [핵심 기능](#-핵심-기능)
- [3-Panel UI](#-3-panel-ui)
- [아키텍처 개요](#-아키텍처-개요)
- [Quick Start](#-quick-start)
- [테스트](#-테스트)
- [API 사용 예시](#-api-사용-예시)
- [환경 변수](#-환경-변수)
- [향후 로드맵](#-향후-로드맵)
- [참고 프로젝트](#-참고-프로젝트)
- [라이선스](#-라이선스)

---

## 📖 프로젝트 소개

**PRD-MiroFish-Lab**은 채팅 기반 PRD(Product Requirements Document) 생성 + 시뮬레이션 검증 시스템입니다.

기존 PRD 작성 프로세스의 문제:
- 빈 문서에서 시작하는 인지적 부담
- 구조화 부족으로 리뷰 시 누락 항목 발견
- 검증 없이 바로 개발 착수 → 후반부 리스크 폭발

**PRD-MiroFish-Lab의 해결 방식:**

```
사용자 대화 → PRD 점진 빌드 → JSON Schema 검증 → Markdown 문서화
                                                        ↓
                                              SimulationSpec 패키징
                                                        ↓
                                     MiroFish 시뮬레이션 검증 (mock/live)
                                                        ↓
                                     ValidationResult (리스크, 누락, 제안)
```

- **채팅만으로** 13개 PRD 섹션을 단계적으로 완성
- **JSON Schema + Pydantic v2** 이중 검증으로 구조적 완전성 보장
- **MiroFish 연동**으로 이해관계자 시뮬레이션 기반 사전 검증
- **체크포인트 시스템**으로 언제든 이전 상태로 되돌리기 가능

---

## ✨ 핵심 기능

### 1. 채팅 기반 PRD 생성

자연어 대화로 13개 섹션을 점진적으로 채웁니다. 5-phase 상태머신이 대화 흐름을 자동 관리합니다.

```
GREETING → INTERVIEWING → REVIEWING → READY_FOR_VALIDATION → VALIDATED
   │            │              │                                  │
   │      (5턴 대화)    "수정할래요"                         "수정할래요"
   │            │              │                                  │
   │            ◄──────────────┘                                  │
   │                                                              │
   │            ◄─────────────────────────────────────────────────┘
```

**PRD 13개 필수 섹션:** metadata, product, users, problem, solution, scope, requirements, success_metrics, delivery, assumptions, risks, open_questions, validation

### 2. JSON Schema 이중 검증

`PRD_SCHEMA.json`(Draft-07)을 single source of truth로 사용합니다.

- **Layer 1:** JSON Schema 검증 — additionalProperties, required, enum 제약
- **Layer 2:** Pydantic v2 검증 — 타입 안전성, 필드 제약

위반 시 구조화된 에러(path, message, validator keyword)를 반환합니다.

### 3. 결정론적 Markdown 렌더링

PRD dict → GFM Markdown 순수 함수. 같은 입력이면 항상 같은 출력.

- 14개 섹션 **고정 순서** (PRD_SCHEMA.json 기준)
- **다국어 헤딩** (ko-KR 기본, en-US 전환)
- **GFM pipe table** (features, requirements, risks, metrics, stakeholders)
- **부분 PRD 처리** (미입력 섹션 skip/placeholder)

### 4. SimulationSpec 패키징

PRDDocument를 MiroFish가 이해할 수 있는 시뮬레이션 입력으로 변환합니다.

- `focus_areas` 자동 추출 (risks 타이틀 + open_questions 텍스트)
- `prd_markdown` + `prd_structured` 동시 포함
- `validation_config`에 goals, stakeholders, simulation_requirement 포함

### 5. Content-aware 검증 엔진

PRD 내용을 분석하여 **7개 검증 결과 필드**를 자동 생성합니다 (하드코딩 아님):

| 필드 | 생성 근거 |
|------|----------|
| `summary` | product name + 첫 번째 goal |
| `top_risks` | focus_areas에서 risk 항목 필터 |
| `missing_requirements` | NFR 부족, acceptance_criteria 누락 감지 |
| `stakeholder_objections` | persona별 review_angle 기반 |
| `scope_adjustments` | timeline_confidence + mvp_in_scope 수 비교 |
| `recommended_questions` | must_answer_questions + focus_areas 질문 |
| `rewrite_suggestions` | 빈 optional 필드(user_journey, AC 등) 감지 |

### 6. MiroFish Async Adapter

`.env` 한 줄로 mock ↔ live 전환:

```bash
MIROFISH_MODE=mock   # 기본값: 즉시 동작, 서버 불필요
MIROFISH_MODE=live   # 실제 MiroFish 서버 연결
```

- MiroFish 다단계 API(`create → prepare → poll → run → get_result`) 전체 lifecycle 자동 관리
- 지수 백오프 retry (1s → 2s → 4s)
- live 모드 실패 시 mock 자동 fallback (`MIROFISH_FALLBACK_TO_MOCK=true`)

---

## 🖥️ 3-Panel UI

```
┌─────────────────────────────────────────────────────────────────┐
│  Header: PRD MiroFish Lab  │  Phase: INTERVIEWING  │  ⚙ 설정   │
├──────────────┬──────────────────────┬───────────────────────────┤
│              │                      │                           │
│  ChatPanel   │    PRDPreview        │   ValidationPanel         │
│              │                      │                           │
│  💬 대화 버블 │  📄 Markdown 렌더링   │  ⚡ 검증 결과 7개 항목     │
│  🏷️ Phase   │  📊 진행률 바         │  📋 Accordion 표시        │
│  🎯 Actions │  🔄 MD↔JSON 토글     │  💡 추천 질문 클릭→채팅    │
│  ❓ 추천 질문 │  ✅ 섹션 체크리스트   │  🔧 수정 제안             │
│              │                      │                           │
├──────────────┴──────────────────────┴───────────────────────────┤
│  Footer: Progress ████████░░ 62% (8/13)        │ 💾 Checkpoint │
└─────────────────────────────────────────────────────────────────┘
```

| 기능 | 설명 |
|------|------|
| **반응형** | 데스크톱 3-column, 태블릿 2-column, 모바일 1-column |
| **다크 모드** | `prefers-color-scheme` 자동 전환 |
| **Phase 배지** | GREETING(파랑), INTERVIEWING(주황), REVIEWING(보라), READY(초록), VALIDATED(금색) |
| **체크포인트** | 자동(phase 전이 시) + 수동(버튼 클릭) + 복원(목록에서 선택) |
| **Cross-panel** | ValidationPanel의 추천 질문 클릭 → ChatPanel 입력창 자동 채움 |

---

## 🏗️ 아키텍처 개요

```
┌─────────────────────── Frontend (apps/web) ───────────────────────┐
│  React 19 + TypeScript 5.9 + Vite 8                               │
│                                                                    │
│  src/types/      백엔드 1:1 대응 TypeScript 타입                    │
│  src/api/        중앙집중 API 클라이언트 (native fetch, 9 함수)      │
│  src/hooks/      useChat, useValidation, useCheckpoints            │
│  src/components/ ChatPanel, PRDPreview, ValidationPanel + 2 공유    │
│  src/styles/     CSS Modules + 다크 모드                            │
│                                                                    │
├────────────────── Backend API (11 endpoints) ─────────────────────┤
│  FastAPI + Pydantic v2 + httpx                                     │
│                                                                    │
│  Chat (6):   sessions CRUD, message, checkpoint, restore           │
│  Validation (3): run, package, schema-check                        │
│  Infra (2):  root, health                                          │
│                                                                    │
├──────────────── Backend Services (10 modules) ────────────────────┤
│                                                                    │
│  session_store ─── conversation_state (상태머신 + 체크포인트)        │
│       ↓                                                            │
│  prd_generator ─── mock_prd_builder (5턴 점진 빌드)                 │
│       ↓                completeness (13 섹션 진행률)                │
│  markdown_renderer (GFM 렌더러)                                     │
│       ↓                                                            │
│  validation_packager (SimulationSpec 포장)                          │
│       ↓                                                            │
│  mirofish_client ─── mock_validation_engine (Content-aware 검증)   │
│       └───────────── mirofish_adapter (Async HTTP, mock↔live)      │
│                                                                    │
├──────────────── Data Contract (Single Source of Truth) ────────────┤
│  PRD_SCHEMA.json   532줄 | 14 required sections | 12 enums        │
│                    9 reusable $defs | additionalProperties: false   │
└────────────────────────────────────────────────────────────────────┘
```

### 주요 기술 스택

| 영역 | 기술 |
|------|------|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, httpx, jsonschema |
| **Frontend** | React 19, TypeScript 5.9, Vite 8, react-markdown |
| **Schema** | JSON Schema Draft-07 |
| **테스트** | pytest, respx (HTTP mocking) |
| **인프라** | Docker, Docker Compose |

---

## 🚀 Quick Start

### 1. 저장소 클론

```bash
git clone https://github.com/kyrios05/prd-mirofish-lab.git
cd prd-mirofish-lab
```

### 2. Backend 실행

```bash
cd apps/api
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

> API docs: http://localhost:8000/docs

### 3. Frontend 실행 (새 터미널)

```bash
cd apps/web
npm install
npm run dev
```

> UI: http://localhost:5173

### 4. 브라우저에서 사용

1. http://localhost:5173 접속 → 자동 세션 생성
2. 채팅으로 PRD 작성 시작
3. 5턴 대화 후 PRD 완성 → 검증 실행

### Docker로 한번에 실행 (선택)

```bash
docker compose up
```

---

## 🧪 테스트

```bash
cd apps/api
pip install -e ".[dev]"
pytest -v
```

### 테스트 현황: **530 passed, 0 failed**

| 모듈 | 테스트 수 | 커버리지 |
|------|----------|---------|
| JSON Schema Validator | 31 | schema 로딩, valid/invalid fixtures, edge cases |
| Chat API & Session | 48 | 세션 CRUD, 대화 계약, mock 진행, completeness |
| Markdown Renderer | 82 | 결정론성, 부분 PRD, 다국어, 테이블, API 통합 |
| Validation Packager | 79 | 패키징, focus_areas, spec 구조, 엔드포인트 |
| Mock Validation Engine | 88 | 7개 builder, content-awareness, 결정론성 |
| Conversation State Machine | 105 | 상태 전이, 체크포인트, auto-advance, T03 회귀 |
| MiroFish Async Adapter | 97 | adapter lifecycle, retry, mode 전환, fallback |

---

## 📡 API 사용 예시

### 세션 생성 + 대화

```bash
# 1. 세션 생성
SESSION=$(curl -s -X POST http://localhost:8000/chat/sessions | jq -r '.session_id')

# 2. 메시지 전송
curl -s -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\", \"message\": \"AI 기반 PRD 생성 도구를 만들려고 해\"}" | jq .
```

**응답 예시:**
```json
{
  "session_id": "a1b2c3d4-...",
  "assistant_message": "좋은 아이디어네요! 제품 이름과 카테고리를 알려주세요.",
  "structured_prd": { "schema_version": "0.1.0", "metadata": {}, "product": {} },
  "prd_markdown": "# MiroFish Lab — PRD v1\n## 메타데이터\n...",
  "draft_status": "incomplete",
  "completeness": { "filled": ["metadata", "product"], "missing": ["..."], "progress": 0.15 },
  "next_questions": ["타겟 사용자는 누구인가요?", "핵심 문제는 무엇인가요?"],
  "current_phase": "interviewing",
  "available_actions": ["continue", "skip_section", "save_checkpoint"]
}
```

### PRD 검증

```bash
curl -s -X POST http://localhost:8000/validation/run \
  -H "Content-Type: application/json" \
  -d '{"project_id": "proj-001", "prd": {"schema_version": "0.1.0", "..."}}' | jq .
```

**응답 예시:**
```json
{
  "project_id": "proj-001",
  "schema_valid": true,
  "status": "completed",
  "validation_mode": "mock",
  "result": {
    "summary": "MiroFish Lab PRD는 MVP 범위 검증 기준 3개 주요 리스크를 발견...",
    "top_risks": ["LLM 응답 품질 불안정", "MiroFish API SLA 미확인"],
    "missing_requirements": ["acceptance_criteria 누락", "integrations 미정의"],
    "stakeholder_objections": ["Engineering Lead: 기술적 복잡도 우려"],
    "scope_adjustments": ["timeline_confidence가 low이므로 MVP 범위 50% 축소 권장"],
    "recommended_questions": ["MiroFish API SLA는 어느 수준인가?"],
    "rewrite_suggestions": ["user_journey 섹션을 추가하면 제품 흐름 이해가 향상됩니다"]
  }
}
```

### 체크포인트

```bash
# 저장
curl -s -X POST http://localhost:8000/chat/sessions/$SESSION/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"label": "users+problem 완성 후"}'

# 목록 조회
curl -s http://localhost:8000/chat/sessions/$SESSION/checkpoints | jq .

# 복원
curl -s -X POST http://localhost:8000/chat/sessions/$SESSION/restore \
  -H "Content-Type: application/json" \
  -d '{"checkpoint_id": "CHECKPOINT_ID"}'
```

---

## ⚙️ 환경 변수

`apps/api/.env` 파일을 생성하세요 (`.env.example` 참고):

```bash
# ─── MiroFish 연결 (선택, 기본값은 mock 모드) ───
MIROFISH_MODE=mock                    # mock (기본) | live
MIROFISH_BASE_URL=http://localhost:5001
MIROFISH_API_KEY=
MIROFISH_FALLBACK_TO_MOCK=true        # live 실패 시 mock fallback
MIROFISH_TIMEOUT=30
MIROFISH_POLLING_INTERVAL=2.0
MIROFISH_MAX_POLLING=150

# ─── LLM (향후 확장) ───
OPENAI_API_BASE=
OPENAI_API_KEY=
```

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MIROFISH_MODE` | `mock` | `mock`: 내장 엔진 사용 / `live`: 실제 MiroFish 연결 |
| `MIROFISH_BASE_URL` | `http://localhost:5001` | MiroFish 서버 주소 |
| `MIROFISH_FALLBACK_TO_MOCK` | `true` | live 모드 실패 시 mock으로 자동 전환 |
| `MIROFISH_TIMEOUT` | `30` | HTTP 요청 타임아웃 (초) |
| `MIROFISH_POLLING_INTERVAL` | `2.0` | 시뮬레이션 상태 폴링 간격 (초) |
| `MIROFISH_MAX_POLLING` | `150` | 최대 폴링 횟수 (초과 시 타임아웃) |

---

## 🗺️ 향후 로드맵

| 우선순위 | 작업 | 설명 |
|---------|------|------|
| 🔴 높음 | **실제 LLM 연결** | mock PRD builder → OpenAI/Claude 기반 자연어 대화 |
| 🔴 높음 | **MiroFish 실제 연동** | `MIROFISH_MODE=live` 실전 테스트 및 응답 매핑 검증 |
| 🟡 중간 | **세션 영속화** | in-memory → Redis/PostgreSQL |
| 🟡 중간 | **사용자 인증** | OAuth/JWT 멀티유저 지원 |
| 🟢 낮음 | **PRD 내보내기** | Markdown → PDF/DOCX |
| 🟢 낮음 | **PRD 버전 관리** | v1 → v2 → v3 diff 이력 추적 |

---

## 🔗 참고 프로젝트

- **[MiroFish](https://github.com/666ghj/MiroFish)** — Swarm Intelligence Engine. 다중 에이전트 시뮬레이션 기반 예측 엔진.
- **[OASIS](https://github.com/camel-ai/oasis)** — Open Agent Social Interaction Simulations. MiroFish 시뮬레이션 엔진의 기반.

---

## 📄 라이선스

MIT License — 자유롭게 사용, 수정, 배포할 수 있습니다.
