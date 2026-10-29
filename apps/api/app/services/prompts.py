"""
app/services/prompts.py — Centralized LLM prompts and response parsing.
"""

from typing import Any
import json
import logging
import re

logger = logging.getLogger(__name__)

_GREETING_ONLY_PATTERN = re.compile(
    r"^\s*(?:안녕(?:하세요)?|반갑습니다?|hello|hi|hey)\s*[!.?~👋😊]*\s*$",
    re.IGNORECASE,
)

SYSTEM_PROMPT_TEMPLATE = """당신은 사용자의 아이디어를 구체적인 PRD(제품 요구사항 정의서)로 변환해주는 'MiroFish PRD Lab'의 수석 제품 기획자 AI입니다.

[작업 규칙 - 필독]
1. 답변 구성: 반드시 [대화 텍스트]를 먼저 작성하고, [JSON 블록]은 답변의 가장 마지막에 작성하세요.
2. 대화 텍스트: 친절한 한국어로 전문가답게 대화하세요. 사용자의 전문 용어나 수치(예: 50ms, MCP 등)를 적극 반영하세요.
3. JSON 블록: 
   - 반드시 ```json ... ``` 코드 블록 내부에 작성하세요.
   - **아래 정의된 SCHEMA 구조를 단 1개의 필드명도 틀리지 말고 엄격히 준수하세요.** 
   - 기존 데이터를 삭제하지 말고 누적하여 업데이트하세요.
   - 불필요한 필드를 직접 지어내지 마세요.
   - 사용자가 제공한 사실로 뒷받침되는 필드만 포함하세요. 인사, 확인, 질문처럼 제품 정보를 제공하지 않은 메시지에는 반드시 빈 객체(`{{}}`)만 반환하세요.
   - 누락된 PRD 섹션을 추측해 채우거나 완성도를 높이지 마세요.

[PRD_SCHEMA.json 엄격 준수 가이드]
반드시 아래 키(Key) 이름과 구조를 사용해야 합니다:
- metadata: {{"project_id": "str", "created_at": "ISO-date", "updated_at": "ISO-date", "language": "ko-KR", "status": "drafting", "source": {{"mode": "chat", "session_id": "uuid"}}, "version": "0.1"}}
- product: {{"name": "str", "one_liner": "한 줄 요약", "category": "str", "platforms": ["web", "mobile"], "stage": "idea"}}
- users: {{"primary_personas": [{{ "name": "str", "role": "str", "goals": ["str"], "pain_points": ["str"] }}], "secondary_personas": [], "non_targets": []}}
- problem: {{"core_problem": "str", "pain_points": ["str"], "current_alternatives": ["str"], "why_now": "str"}}
- solution: {{"summary": "str", "value_proposition": "str", "key_features": [{{ "name": "str", "description": "str", "priority": "must_have" }}], "user_journey": []}}
- scope: {{"mvp_in_scope": ["str"], "out_of_scope": ["str"], "future_expansion": []}}
- requirements: {{"functional": [{{ "id": "FR-01", "statement": "str", "priority": "high" }}], "non_functional": [{{ "id": "NFR-01", "statement": "str", "priority": "medium" }}]}}
- success_metrics: {{"north_star": "str", "product_metrics": [{{ "name": "str", "target": "str" }}]}}
- delivery: {{"priority": "high", "timeline_confidence": "medium", "target_release": "YYYY-MM-DD"}}
- assumptions: [{{ "text": "str", "tag": "str" }}]
- risks: [{{ "title": "str", "description": "str", "severity": "medium", "mitigation": "str" }}]
- open_questions: [{{ "text": "str" }}]
- validation: {{"goals": ["str"], "stakeholder_personas": [{{ "name": "str", "role": "str", "review_angle": "str" }}], "simulation_requirement": "str"}}

[현재 PRD 상태]
{draft_context}
"""

def build_system_prompt(current_prd_draft: dict[str, Any]) -> str:
    draft_str = json.dumps(current_prd_draft, indent=2, ensure_ascii=False)
    return SYSTEM_PROMPT_TEMPLATE.format(draft_context=draft_str)


def is_greeting_only(message: str) -> bool:
    """Return whether a message is a greeting without product information."""
    return bool(_GREETING_ONLY_PATTERN.fullmatch(message))


def extract_prd_json(text: str) -> dict[str, Any]:
    """
    Extract the PRD JSON object from an LLM response.

    Prefers a fenced ```json block (what the system prompt asks for), and falls
    back to the outermost {...} span for models that ignore the fence. Returns
    an empty dict when nothing parseable is present — callers treat that as
    "no delta this turn" rather than an error.

    Shared by all LLM backends (ollama / claude / openai) so provider swaps
    cannot change how responses are parsed.
    """
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extracted JSON: {e}")
            return {}

    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        pass

    return {}
