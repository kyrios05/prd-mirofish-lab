# 🏗️ PRD-MiroFish-Lab Architecture

> **C4 Model 기반 아키텍처 문서** — [Structurizr DSL](../workspace.dsl)에서 자동 생성

이 문서는 PRD-MiroFish-Lab의 아키텍처를 C4 Model의 4단계로 설명합니다.

---

## 📑 목차

- [Level 1: System Context](#level-1-system-context)
- [Level 2: Containers](#level-2-containers)
- [Level 3: Frontend Components](#level-3-frontend-components)
- [Level 3: Backend Services Components](#level-3-backend-services-components)
- [데이터 흐름](#데이터-흐름)
- [Structurizr DSL 사용법](#structurizr-dsl-사용법)

---

## Level 1: System Context

> 사용자, PRD-MiroFish-Lab 시스템, 외부 서비스 간의 관계

```mermaid
graph TB
  linkStyle default fill:#ffffff

  subgraph diagram ["PRD-MiroFish-Lab — System Context (C4 Level 1)"]
    style diagram fill:#ffffff,stroke:#ffffff

    1["<div style='font-weight: bold'>Product Manager</div><div style='font-size: 70%; margin-top: 0px'>[Person]</div><div style='font-size: 80%; margin-top:10px'>채팅으로 PRD를 작성하고 검증 결과를 확인하는<br />사용자</div>"]
    style 1 fill:#08427b,stroke:#052e56,color:#ffffff
    2("<div style='font-weight: bold'>MiroFish</div><div style='font-size: 70%; margin-top: 0px'>[Software System]</div><div style='font-size: 80%; margin-top:10px'>다중 에이전트 Swarm Intelligence<br />시뮬레이션 엔진<br />https://github.com/666ghj/MiroFish</div>")
    style 2 fill:#999999,stroke:#6b6b6b,color:#ffffff
    3("<div style='font-weight: bold'>LLM Service</div><div style='font-size: 70%; margin-top: 0px'>[Software System]</div><div style='font-size: 80%; margin-top:10px'>OpenAI / Claude 등 LLM API (향후<br />연동 예정, 현재 mock)</div>")
    style 3 fill:#cccccc,stroke:#8e8e8e,color:#666666
    4("<div style='font-weight: bold'>PRD-MiroFish-Lab</div><div style='font-size: 70%; margin-top: 0px'>[Software System]</div><div style='font-size: 80%; margin-top:10px'>채팅으로 구조화된 PRD를 생성하고 MiroFish<br />시뮬레이션으로 검증하는 시스템</div>")
    style 4 fill:#1168bd,stroke:#0b4884,color:#ffffff

    1-. "<div>채팅으로 PRD 작성 및 검증</div><div style='font-size: 70%'>[HTTPS]</div>" .->4
    4-. "<div>시뮬레이션 검증 요청 (live 모드)</div><div style='font-size: 70%'>[HTTP API]</div>" .->2
    4-. "<div>PRD 생성 대화 (향후)</div><div style='font-size: 70%'>[HTTP API]</div>" .->3

  end
```

**설명:**
- **Product Manager**: 브라우저에서 3-Panel UI를 통해 채팅으로 PRD를 작성
- **PRD-MiroFish-Lab**: 핵심 시스템 — 채팅 → PRD 생성 → 검증 파이프라인
- **MiroFish**: 외부 시뮬레이션 엔진 (live 모드에서만 호출, 기본은 mock)
- **LLM Service**: 향후 연동 예정 (현재 deterministic mock builder 사용)

---

## Level 2: Containers

> Frontend, Backend API, Services, Schema Validator, Data Contract

```mermaid
graph TB
  linkStyle default fill:#ffffff

  subgraph diagram ["PRD-MiroFish-Lab — Containers (C4 Level 2)"]
    style diagram fill:#ffffff,stroke:#ffffff

    1["<div style='font-weight: bold'>Product Manager</div><div style='font-size: 70%; margin-top: 0px'>[Person]</div><div style='font-size: 80%; margin-top:10px'>채팅으로 PRD를 작성하고 검증 결과를 확인하는<br />사용자</div>"]
    style 1 fill:#08427b,stroke:#052e56,color:#ffffff
    2("<div style='font-weight: bold'>MiroFish</div><div style='font-size: 70%; margin-top: 0px'>[Software System]</div><div style='font-size: 80%; margin-top:10px'>다중 에이전트 Swarm Intelligence<br />시뮬레이션 엔진<br />https://github.com/666ghj/MiroFish</div>")
    style 2 fill:#999999,stroke:#6b6b6b,color:#ffffff

    subgraph 4 ["PRD-MiroFish-Lab"]
      style 4 fill:#ffffff,stroke:#0b4884,color:#0b4884

      5["<div style='font-weight: bold'>Web Frontend</div><div style='font-size: 70%; margin-top: 0px'>[Container: React SPA]</div><div style='font-size: 80%; margin-top:10px'>3-Panel UI (Chat / PRD<br />Preview / Validation) React<br />19, TypeScript 5.9, Vite 8</div>"]
      style 5 fill:#438dd5,stroke:#2e6295,color:#ffffff
      14["<div style='font-weight: bold'>Backend API</div><div style='font-size: 70%; margin-top: 0px'>[Container: FastAPI]</div><div style='font-size: 80%; margin-top:10px'>FastAPI 서버 (11 endpoints)<br />Python 3.11+, Pydantic v2</div>"]
      style 14 fill:#438dd5,stroke:#2e6295,color:#ffffff
      18["<div style='font-weight: bold'>Backend Services</div><div style='font-size: 70%; margin-top: 0px'>[Container: Python]</div><div style='font-size: 80%; margin-top:10px'>비즈니스 로직 계층 10개 서비스 모듈</div>"]
      style 18 fill:#85bbf0,stroke:#5d82a8,color:#000000
      30["<div style='font-weight: bold'>Schema Validator</div><div style='font-size: 70%; margin-top: 0px'>[Container: Python / jsonschema]</div><div style='font-size: 80%; margin-top:10px'>JSON Schema Draft7Validator<br />lru_cache 싱글톤 validate_prd()<br />→ ValidationReport</div>"]
      style 30 fill:#85bbf0,stroke:#5d82a8,color:#000000
      29[("<div style='font-weight: bold'>Data Contract</div><div style='font-size: 70%; margin-top: 0px'>[Container: JSON Schema Draft-07]</div><div style='font-size: 80%; margin-top:10px'>PRD_SCHEMA.json (532줄) 14<br />required sections, 12 enums,<br />9 reusable $defs Single<br />Source of Truth</div>")]
      style 29 fill:#f5a623,stroke:#ab7418,color:#000000
    end

    1-. "<div>브라우저에서 3-Panel UI 사용</div><div style='font-size: 70%'>[HTTPS]</div>" .->5
    5-. "<div>Chat API 호출</div><div style='font-size: 70%'>[HTTP/JSON]</div>" .->14
    14-. "<div>세션 조회/저장</div><div style='font-size: 70%'></div>" .->18
    14-. "<div>JSON Schema 검증</div><div style='font-size: 70%'></div>" .->30
    18-. "<div>HTTP API 호출</div><div style='font-size: 70%'>[httpx]</div>" .->2
    30-. "<div>스키마 로드 (lru_cache)</div><div style='font-size: 70%'></div>" .->29
    18-. "<div>모델 구조 준수</div><div style='font-size: 70%'></div>" .->29

  end
```

**컨테이너 요약:**

| 컨테이너 | 기술 | 역할 |
|----------|------|------|
| **Web Frontend** | React 19, TypeScript, Vite | 3-Panel UI (Chat, PRD Preview, Validation) |
| **Backend API** | FastAPI, Pydantic v2 | 11개 REST 엔드포인트 |
| **Backend Services** | Python 3.11+ | 10개 비즈니스 로직 모듈 |
| **Schema Validator** | jsonschema Draft-07 | PRD 구조 검증 (lru_cache 싱글톤) |
| **Data Contract** | PRD_SCHEMA.json | 14 required sections, 12 enums, 9 $defs |

---

## Level 3: Frontend Components

> React 컴포넌트, Hooks, API Client, Domain Types

```mermaid
graph TB
  linkStyle default fill:#ffffff

  subgraph diagram ["Frontend — Components (C4 Level 3)"]
    style diagram fill:#ffffff,stroke:#ffffff

    subgraph 5 ["Web Frontend"]
      style 5 fill:#ffffff,stroke:#2e6295,color:#2e6295

      6["<div style='font-weight: bold'>ChatPanel</div><div style='font-size: 70%; margin-top: 0px'>[React Component]</div><div style='font-size: 80%; margin-top:10px'>대화 버블, 메시지 입력, Phase 배지,<br />available_actions,<br />next_questions 자동 채움</div>"]
      style 6 fill:#85bbf0,stroke:#5d82a8,color:#000000
      7["<div style='font-weight: bold'>PRDPreview</div><div style='font-size: 70%; margin-top: 0px'>[React Component]</div><div style='font-size: 80%; margin-top:10px'>Markdown 렌더링, MD↔JSON 토글, 진행률<br />바, 섹션 체크리스트</div>"]
      style 7 fill:#85bbf0,stroke:#5d82a8,color:#000000
      8["<div style='font-weight: bold'>ValidationPanel</div><div style='font-size: 70%; margin-top: 0px'>[React Component]</div><div style='font-size: 80%; margin-top:10px'>검증 실행 버튼, ValidationResult 7개<br />필드 Accordion, 추천 질문→ChatPanel<br />연결</div>"]
      style 8 fill:#85bbf0,stroke:#5d82a8,color:#000000
      9["<div style='font-weight: bold'>CheckpointModal</div><div style='font-size: 70%; margin-top: 0px'>[React Component]</div><div style='font-size: 80%; margin-top:10px'>체크포인트 저장/목록/복원 UI</div>"]
      style 9 fill:#85bbf0,stroke:#5d82a8,color:#000000
      12["<div style='font-weight: bold'>useChat Hook</div><div style='font-size: 70%; margin-top: 0px'>[React Hook]</div><div style='font-size: 80%; margin-top:10px'>세션 관리, 메시지 전송,<br />phase/completeness 상태</div>"]
      style 12 fill:#85bbf0,stroke:#5d82a8,color:#000000
      13["<div style='font-weight: bold'>useValidation Hook</div><div style='font-size: 70%; margin-top: 0px'>[React Hook]</div><div style='font-size: 80%; margin-top:10px'>검증 실행, 결과 상태 관리</div>"]
      style 13 fill:#85bbf0,stroke:#5d82a8,color:#000000
      10["<div style='font-weight: bold'>API Client</div><div style='font-size: 70%; margin-top: 0px'>[TypeScript Module]</div><div style='font-size: 80%; margin-top:10px'>중앙집중 HTTP 클라이언트 native fetch,<br />ApiError, 9 함수</div>"]
      style 10 fill:#85bbf0,stroke:#5d82a8,color:#000000
      11["<div style='font-weight: bold'>Domain Types</div><div style='font-size: 70%; margin-top: 0px'>[TypeScript Module]</div><div style='font-size: 80%; margin-top:10px'>백엔드 1:1 대응 TypeScript 타입<br />prd.ts, chat.ts,<br />validation.ts</div>"]
      style 11 fill:#85bbf0,stroke:#5d82a8,color:#000000
    end

    14["<div style='font-weight: bold'>Backend API</div><div style='font-size: 70%; margin-top: 0px'>[Container: FastAPI]</div><div style='font-size: 80%; margin-top:10px'>FastAPI 서버 (11 endpoints)<br />Python 3.11+, Pydantic v2</div>"]
    style 14 fill:#438dd5,stroke:#2e6295,color:#ffffff

    6-. "메시지 전송/수신" .->12
    7-. "structured_prd, prd_markdown 구독" .->12
    8-. "검증 실행/결과 구독" .->13
    8-. "추천 질문 → 입력창 자동 채움" .->6
    9-. "checkpoint CRUD" .->10
    12-. "createSession, sendMessage" .->10
    13-. "runValidation" .->10
    10-. "타입 참조" .->11
    10-. "Chat/Validation API 호출 [HTTP/JSON]" .->14

  end
```

---

## Level 3: Backend Services Components

> 10개 서비스 모듈 간의 의존 관계

```mermaid
graph TB
  linkStyle default fill:#ffffff

  subgraph diagram ["Backend Services — Components (C4 Level 3)"]
    style diagram fill:#ffffff,stroke:#ffffff

    2("<div style='font-weight: bold'>MiroFish</div><div style='font-size: 70%; margin-top: 0px'>[External System]</div><div style='font-size: 80%; margin-top:10px'>다중 에이전트 시뮬레이션 엔진</div>")
    style 2 fill:#999999,stroke:#6b6b6b,color:#ffffff

    subgraph 18 ["Backend Services"]
      style 18 fill:#ffffff,stroke:#5d82a8,color:#5d82a8

      19["<div style='font-weight: bold'>Session Store</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>인메모리 세션 관리<br />Singleton</div>"]
      style 19 fill:#85bbf0,stroke:#5d82a8,color:#000000
      20["<div style='font-weight: bold'>Conversation State</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>5-Phase 상태머신<br />체크포인트 save/restore</div>"]
      style 20 fill:#85bbf0,stroke:#5d82a8,color:#000000
      21["<div style='font-weight: bold'>PRD Generator</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>PRD 생성 오케스트레이터</div>"]
      style 21 fill:#85bbf0,stroke:#5d82a8,color:#000000
      22["<div style='font-weight: bold'>Mock PRD Builder</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>5턴 점진 빌드<br />결정론적</div>"]
      style 22 fill:#85bbf0,stroke:#5d82a8,color:#000000
      23["<div style='font-weight: bold'>Completeness</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>13 섹션 진행률</div>"]
      style 23 fill:#85bbf0,stroke:#5d82a8,color:#000000
      24["<div style='font-weight: bold'>Markdown Renderer</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>GFM Markdown 렌더러<br />순수 함수, 다국어</div>"]
      style 24 fill:#85bbf0,stroke:#5d82a8,color:#000000
      25["<div style='font-weight: bold'>Validation Packager</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>PRD → SimulationSpec</div>"]
      style 25 fill:#85bbf0,stroke:#5d82a8,color:#000000
      26["<div style='font-weight: bold'>Mock Validation Engine</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>Content-aware 검증<br />7개 필드 생성</div>"]
      style 26 fill:#85bbf0,stroke:#5d82a8,color:#000000
      27["<div style='font-weight: bold'>MiroFish Adapter</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>Async HTTP adapter<br />retry/backoff, polling</div>"]
      style 27 fill:#85bbf0,stroke:#5d82a8,color:#000000
      28["<div style='font-weight: bold'>MiroFish Client</div><div style='font-size: 70%'>[Python Module]</div><div style='font-size: 80%; margin-top:10px'>mock ↔ live 전환<br />fallback 지원</div>"]
      style 28 fill:#85bbf0,stroke:#5d82a8,color:#000000
    end

    14["<div style='font-weight: bold'>Backend API</div><div style='font-size: 70%'>[FastAPI]</div>"]
    style 14 fill:#438dd5,stroke:#2e6295,color:#ffffff
    29[("<div style='font-weight: bold'>PRD_SCHEMA.json</div><div style='font-size: 70%'>[Data Contract]</div>")]
    style 29 fill:#f5a623,stroke:#ab7418,color:#000000

    14 --> 19
    14 --> 20
    14 --> 21
    14 --> 23
    14 --> 24
    14 --> 25
    14 --> 28
    21 --> 19
    21 --> 22
    20 --> 19
    25 --> 24
    28 --> 26
    28 --> 27
    27 --> 2
    22 --> 29
    25 --> 29

  end
```

---

## 데이터 흐름

### 채팅 → PRD 생성 → 검증 전체 흐름

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant CP as ChatPanel
    participant API as Backend API
    participant SS as Session Store
    participant CSM as State Machine
    participant PG as PRD Generator
    participant MR as Markdown Renderer
    participant CE as Completeness
    participant VP as Validation Packager
    participant MC as MiroFish Client
    participant MVE as Mock Engine

    U->>CP: 메시지 입력
    CP->>API: POST /chat/message
    API->>SS: get_session()
    API->>CSM: phase 확인 + auto_advance
    API->>PG: update_from_message()
    PG->>SS: current_prd_draft.update(delta)
    API->>CE: calculate_completeness()
    API->>MR: render_prd_markdown()
    API-->>CP: ChatResponse (prd + markdown + phase + actions)
    CP-->>U: 대화 버블 + PRD 미리보기

    Note over U,MVE: PRD 완성 후 (progress == 1.0)

    U->>API: POST /validation/run
    API->>VP: package_for_simulation()
    VP->>MR: render_prd_markdown()
    VP-->>API: SimulationSpec
    API->>MC: run_validation(spec)
    alt mock 모드
        MC->>MVE: run_mock_validation(spec)
        MVE-->>MC: ValidationResult (7 fields)
    else live 모드
        MC->>MC: MiroFish Adapter → HTTP API
    end
    MC-->>API: ValidationResult
    API-->>U: ValidationResponse (result + spec)
```

---

## Structurizr DSL 사용법

### 소스 파일

```
workspace.dsl          ← Structurizr DSL (Single Source of Truth)
docs/ARCHITECTURE.md   ← 이 문서 (Mermaid 다이어그램 포함)
```

### 로컬에서 Structurizr Lite로 보기

```bash
# Docker로 Structurizr Lite 실행
docker run -it --rm -p 8080:8080 \
  -v $(pwd):/usr/local/structurizr \
  structurizr/lite

# 브라우저에서 http://localhost:8080 접속
```

### Structurizr CLI로 다이어그램 내보내기

```bash
# Mermaid 포맷 (GitHub 렌더링용)
structurizr-cli export -workspace workspace.dsl -format mermaid -output docs/

# PlantUML 포맷
structurizr-cli export -workspace workspace.dsl -format plantuml/c4plantuml -output docs/

# DSL 검증
structurizr-cli validate -workspace workspace.dsl
```

### 온라인 뷰어

[Structurizr DSL Editor](https://structurizr.com/dsl)에서 `workspace.dsl` 내용을 붙여넣으면 바로 렌더링됩니다.

---

*이 문서는 `workspace.dsl`에서 생성되었습니다. 아키텍처 변경 시 DSL을 먼저 수정하고 이 문서를 재생성하세요.*
