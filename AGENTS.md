# AGENTS.md — AI Developer Behavior Guidelines

## 기본 원칙

1. **PRD_SCHEMA.json이 항상 이긴다**: 코드와 스키마 간 drift 발생 시, 항상 PRD_SCHEMA.json 기준으로 코드를 수정한다.
2. **Scope Guard**: 각 태스크(T01~T06)의 scope를 엄격히 지킨다. 범위 외 작업은 `TODO(Txx)` 주석으로 표시하고 구현하지 않는다.
3. **Minimum surface**: 지금 필요한 것만 만든다. 과도한 추상화, 미래를 위한 infrastructure는 금지.
4. **앱 기동 최우선**: 모든 작업 후 `uvicorn app.main:app` 기동이 성공해야 한다.

## 파일 구조 규칙

```
apps/api/app/
├── schemas/          ← 모든 도메인 모델 (T01 이후 single source)
│   ├── enums.py      ← Enum 전용 (의존성 없음)
│   ├── common.py     ← 재사용 서브모델 (enums만 import)
│   ├── prd.py        ← 최상위 PRDDocument + 섹션 모델
│   └── __init__.py   ← public re-export
├── models.py         ← T03 전까지 호환 shim (schemas로 redirect)
├── routes/           ← API 엔드포인트
├── services/         ← 비즈니스 로직
├── config.py         ← 설정
└── main.py           ← FastAPI 앱
```

## Import 규칙

- `enums` → 의존성 없음
- `common` → `enums`만 import
- `prd` → `enums`, `common`만 import
- `routes`, `services` → `app.schemas`에서 import (direct)
- 순환 import 금지

## Commit 규칙

- 컨벤셔널 커밋 형식: `type(scope): description`
- 타입: `feat`, `fix`, `refactor`, `docs`, `chore`
- 모든 변경은 즉시 커밋 후 PR 생성

## T01 산출물

- [x] `apps/api/app/schemas/enums.py`
- [x] `apps/api/app/schemas/common.py`
- [x] `apps/api/app/schemas/prd.py`
- [x] `apps/api/app/schemas/__init__.py`
- [x] `apps/api/app/models.py` (shim)
- [x] `apps/api/tests/fixtures/sample_prd_minimal.json`
- [x] `apps/api/tests/fixtures/sample_prd_full.json`
- [x] `PRD_SCHEMA.json`
