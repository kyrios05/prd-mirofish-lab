workspace "PRD-MiroFish-Lab" "채팅 기반 PRD 생성 + MiroFish 시뮬레이션 검증 시스템" {

    !identifiers hierarchical

    model {
        # ── Actors ──
        user = person "Product Manager" "채팅으로 PRD를 작성하고 검증 결과를 확인하는 사용자" "User"

        # ── External Systems ──
        mirofish = softwareSystem "MiroFish" "다중 에이전트 Swarm Intelligence 시뮬레이션 엔진\nhttps://github.com/666ghj/MiroFish" "External"
        llm = softwareSystem "LLM Service" "OpenAI / Claude 등 LLM API\n(향후 연동 예정, 현재 mock)" "External,Future"

        # ── PRD-MiroFish-Lab System ──
        prdLab = softwareSystem "PRD-MiroFish-Lab" "채팅으로 구조화된 PRD를 생성하고\nMiroFish 시뮬레이션으로 검증하는 시스템" {

            # ── Container: Frontend ──
            frontend = container "Web Frontend" "3-Panel UI (Chat / PRD Preview / Validation)\nReact 19, TypeScript 5.9, Vite 8" "React SPA" "Browser" {
                chatPanel = component "ChatPanel" "대화 버블, 메시지 입력, Phase 배지,\navailable_actions, next_questions 자동 채움" "React Component"
                prdPreview = component "PRDPreview" "Markdown 렌더링, MD↔JSON 토글,\n진행률 바, 섹션 체크리스트" "React Component"
                validationPanel = component "ValidationPanel" "검증 실행 버튼, ValidationResult 7개 필드\nAccordion, 추천 질문→ChatPanel 연결" "React Component"
                checkpointModal = component "CheckpointModal" "체크포인트 저장/목록/복원 UI" "React Component"
                apiClient = component "API Client" "중앙집중 HTTP 클라이언트\nnative fetch, ApiError, 9 함수" "TypeScript Module"
                domainTypes = component "Domain Types" "백엔드 1:1 대응 TypeScript 타입\nprd.ts, chat.ts, validation.ts" "TypeScript Module"
                chatHook = component "useChat Hook" "세션 관리, 메시지 전송,\nphase/completeness 상태" "React Hook"
                validationHook = component "useValidation Hook" "검증 실행, 결과 상태 관리" "React Hook"
            }

            # ── Container: Backend API ──
            backend = container "Backend API" "FastAPI 서버 (11 endpoints)\nPython 3.11+, Pydantic v2" "FastAPI" "Server" {
                chatRoutes = component "Chat Routes" "POST /chat/sessions, /chat/message\nGET /chat/sessions/{id}\ncheckpoint/restore endpoints (6개)" "FastAPI Router"
                validationRoutes = component "Validation Routes" "POST /validation/run\nPOST /validation/package\nPOST /validation/schema-check (3개)" "FastAPI Router"
                healthRoute = component "Health Routes" "GET /, GET /health (2개)" "FastAPI Router"
            }

            # ── Container: Backend Services ──
            services = container "Backend Services" "비즈니스 로직 계층\n10개 서비스 모듈" "Python" "Service" {
                sessionStore = component "Session Store" "인메모리 세션 관리\nSessionState, ConversationTurn\nSingleton" "Python Module"
                conversationState = component "Conversation State" "5-Phase 상태머신\nGREETING→INTERVIEWING→REVIEWING→\nREADY_FOR_VALIDATION→VALIDATED\n체크포인트 save/restore" "Python Module"
                prdGenerator = component "PRD Generator" "PRD 생성 오케스트레이터\nsession + mock builder 연결" "Python Module"
                mockPrdBuilder = component "Mock PRD Builder" "5턴 점진 PRD 빌드\nPydantic model_dump() 사용\n결정론적" "Python Module"
                completeness = component "Completeness Engine" "13 섹션 진행률 계산\nDraftStatus, suggest_next_questions" "Python Module"
                markdownRenderer = component "Markdown Renderer" "PRD dict → GFM Markdown\n순수 함수, 다국어, 고정 순서" "Python Module"
                validationPackager = component "Validation Packager" "PRDDocument → SimulationSpec\nfocus_areas 자동 추출" "Python Module"
                mockValidationEngine = component "Mock Validation Engine" "Content-aware ValidationResult 생성\n7개 필드, PRD 데이터 기반" "Python Module"
                mirofishAdapter = component "MiroFish Adapter" "Async HTTP adapter\nhttpx, retry/backoff, polling\ncreate→prepare→run→result" "Python Module"
                mirofishClient = component "MiroFish Client" "mock ↔ live 모드 전환\nfallback_to_mock 지원" "Python Module"
            }

            # ── Container: Schema / Data Contract ──
            schema = container "Data Contract" "PRD_SCHEMA.json (532줄)\n14 required sections, 12 enums,\n9 reusable $defs\nSingle Source of Truth" "JSON Schema Draft-07" "Database"

            # ── Container: Validator ──
            validator = container "Schema Validator" "JSON Schema Draft7Validator\nlru_cache 싱글톤\nvalidate_prd() → ValidationReport" "Python / jsonschema" "Service"
        }

        # ── Relationships: Actor → System ──
        user -> prdLab "채팅으로 PRD 작성 및 검증" "HTTPS"
        prdLab -> mirofish "시뮬레이션 검증 요청 (live 모드)" "HTTP API"
        prdLab -> llm "PRD 생성 대화 (향후)" "HTTP API"

        # ── Relationships: Actor → Container ──
        user -> prdLab.frontend "브라우저에서 3-Panel UI 사용" "HTTPS"

        # ── Relationships: Frontend Internal ──
        prdLab.frontend.chatPanel -> prdLab.frontend.chatHook "메시지 전송/수신"
        prdLab.frontend.prdPreview -> prdLab.frontend.chatHook "structured_prd, prd_markdown 구독"
        prdLab.frontend.validationPanel -> prdLab.frontend.validationHook "검증 실행/결과 구독"
        prdLab.frontend.validationPanel -> prdLab.frontend.chatPanel "추천 질문 → 입력창 자동 채움" "Cross-panel callback"
        prdLab.frontend.checkpointModal -> prdLab.frontend.apiClient "checkpoint CRUD"
        prdLab.frontend.chatHook -> prdLab.frontend.apiClient "createSession, sendMessage"
        prdLab.frontend.validationHook -> prdLab.frontend.apiClient "runValidation"
        prdLab.frontend.apiClient -> prdLab.frontend.domainTypes "타입 참조"

        # ── Relationships: Frontend → Backend ──
        prdLab.frontend.apiClient -> prdLab.backend.chatRoutes "Chat API 호출" "HTTP/JSON"
        prdLab.frontend.apiClient -> prdLab.backend.validationRoutes "Validation API 호출" "HTTP/JSON"

        # ── Relationships: Backend Routes → Services ──
        prdLab.backend.chatRoutes -> prdLab.services.sessionStore "세션 조회/저장"
        prdLab.backend.chatRoutes -> prdLab.services.conversationState "phase 전이, checkpoint"
        prdLab.backend.chatRoutes -> prdLab.services.prdGenerator "update_from_message"
        prdLab.backend.chatRoutes -> prdLab.services.completeness "진행률 계산"
        prdLab.backend.chatRoutes -> prdLab.services.markdownRenderer "prd_markdown 생성"
        prdLab.backend.validationRoutes -> prdLab.validator "JSON Schema 검증"
        prdLab.backend.validationRoutes -> prdLab.services.validationPackager "SimulationSpec 패키징"
        prdLab.backend.validationRoutes -> prdLab.services.mirofishClient "검증 실행"

        # ── Relationships: Services Internal ──
        prdLab.services.prdGenerator -> prdLab.services.sessionStore "세션 상태 읽기/쓰기"
        prdLab.services.prdGenerator -> prdLab.services.mockPrdBuilder "턴별 PRD delta 생성"
        prdLab.services.conversationState -> prdLab.services.sessionStore "phase, checkpoints 저장"
        prdLab.services.validationPackager -> prdLab.services.markdownRenderer "prd_markdown 생성"
        prdLab.services.mirofishClient -> prdLab.services.mockValidationEngine "mock 모드"
        prdLab.services.mirofishClient -> prdLab.services.mirofishAdapter "live 모드"
        prdLab.services.mirofishAdapter -> mirofish "HTTP API 호출" "httpx"

        # ── Relationships: Schema ──
        prdLab.validator -> prdLab.schema "스키마 로드 (lru_cache)"
        prdLab.services.mockPrdBuilder -> prdLab.schema "모델 구조 준수"
        prdLab.services.validationPackager -> prdLab.schema "SimulationSpec 구조"
    }

    views {
        # ── Level 1: System Context ──
        systemContext prdLab "SystemContext" {
            include *
            autoLayout
            title "PRD-MiroFish-Lab — System Context (C4 Level 1)"
            description "사용자, PRD-MiroFish-Lab 시스템, 외부 서비스 간의 관계"
        }

        # ── Level 2: Container ──
        container prdLab "Containers" {
            include *
            autoLayout
            title "PRD-MiroFish-Lab — Containers (C4 Level 2)"
            description "Frontend, Backend API, Services, Schema Validator, Data Contract"
        }

        # ── Level 3: Frontend Components ──
        component prdLab.frontend "FrontendComponents" {
            include *
            autoLayout
            title "Frontend — Components (C4 Level 3)"
            description "React 컴포넌트, Hooks, API Client, Domain Types"
        }

        # ── Level 3: Backend API Components ──
        component prdLab.backend "BackendComponents" {
            include *
            autoLayout
            title "Backend API — Components (C4 Level 3)"
            description "FastAPI 라우터: Chat (6) + Validation (3) + Health (2)"
        }

        # ── Level 3: Backend Services Components ──
        component prdLab.services "ServiceComponents" {
            include *
            autoLayout
            title "Backend Services — Components (C4 Level 3)"
            description "10개 서비스 모듈 간의 의존 관계"
        }

        styles {
            element "Person" {
                shape Person
                background #08427B
                color #ffffff
                fontSize 22
            }
            element "Software System" {
                background #1168BD
                color #ffffff
                shape RoundedBox
            }
            element "External" {
                background #999999
                color #ffffff
            }
            element "Future" {
                background #CCCCCC
                color #666666
                border dashed
            }
            element "Container" {
                background #438DD5
                color #ffffff
            }
            element "Browser" {
                shape WebBrowser
                background #438DD5
                color #ffffff
            }
            element "Server" {
                shape Hexagon
                background #438DD5
                color #ffffff
            }
            element "Service" {
                shape Component
                background #85BBF0
                color #000000
            }
            element "Database" {
                shape Cylinder
                background #F5A623
                color #000000
            }
            element "Component" {
                background #85BBF0
                color #000000
            }
            relationship "Relationship" {
                routing Curved
            }
        }
    }

}
