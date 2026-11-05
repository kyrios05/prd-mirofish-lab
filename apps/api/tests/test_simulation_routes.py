from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.routes import simulation
from app.schemas import Stakeholder


def test_live_proposal_with_too_few_personas_does_not_silently_mock(monkeypatch):
    async def propose_one_persona(_: dict) -> list[Stakeholder]:
        return [
            Stakeholder(
                name="PM 김철수",
                role="Product Manager",
                review_angle="비즈니스 가치 검토",
                likely_objections=["일정 지연 위험"],
            )
        ]

    monkeypatch.setattr(simulation.settings, "mirofish_mode", "live")
    monkeypatch.setattr(
        simulation.mirofish,
        "propose_stakeholders_from_dict",
        propose_one_persona,
    )

    response = TestClient(app).post(
        "/simulation/propose-stakeholders",
        json={"live": True},
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "error"
    assert "Mock 결과로 대체하지 않았습니다" in data["message"]


def test_live_proposal_uses_prd_payload(monkeypatch):
    received_payload: dict = {}

    async def propose_from_prd(payload: dict) -> list[Stakeholder]:
        received_payload.update(payload)
        return [
            Stakeholder(
                name=f"검토자 {index}",
                role="Product Reviewer",
                review_angle="PRD 실행 가능성 검토",
                likely_objections=["인수 기준이 필요합니다"],
            )
            for index in range(simulation.MIN_STAKEHOLDER_COUNT)
        ]

    monkeypatch.setattr(
        simulation.mirofish,
        "propose_stakeholders_from_dict",
        propose_from_prd,
    )

    prd = {"product": {"name": "실시간 검증 서비스"}}
    response = TestClient(app).post(
        "/simulation/propose-stakeholders",
        json={"live": True, "prd": prd},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert received_payload == prd


async def test_mock_stream_runs_multi_round_debate_and_emits_risk_nodes(monkeypatch):
    async def no_sleep(_: float) -> None:
        return None

    personas = [
        {
            "name": f"검토자 {index}",
            "role": "Product Reviewer",
            "review_angle": "핵심 요구사항 검토",
            "likely_objections": [f"리스크 {index}"],
        }
        for index in range(8)
    ]
    monkeypatch.setattr(simulation.asyncio, "sleep", no_sleep)
    state = {"run_id": "test-run", "stakeholder_personas": personas, "prd_snapshot": {}, "derived_risks": []}

    events = []
    async for raw_event in simulation._simulation_event_generator(mode="mock", session_state=state):
        events.append(json.loads(raw_event.removeprefix("data: ").strip()))

    posts = [event for event in events if event["type"] == "agent_post"]
    assert len(posts) == 24
    assert all(event["reply_to"] for event in posts)
    assert all(event.get("claim_reference") for event in posts)
    assert {event.get("round") for event in posts} == {1, 2, 3}
    assert any(
        node["group"] == 4
        for event in posts
        for node in event.get("nodes", [])
    )
    assert any(
        link.get("weight", 0) > 1
        for event in posts
        for link in event.get("links", [])
    )


async def test_live_dialogues_use_prior_rounds_and_derive_risks(monkeypatch):
    personas = [
        {
            "name": name,
            "role": "Product Reviewer",
            "review_angle": "핵심 요구사항 검토",
            "likely_objections": ["검증 기준이 부족합니다"],
        }
        for name in ["김도윤", "강혜원", "박현우"]
    ]

    class StubLlm:
        calls = 0

        async def chat(self, _: list[dict[str, str]]) -> str:
            self.calls += 1
            round_number = self.calls
            dialogues = []
            for index, persona in enumerate(personas):
                speaker = persona["name"]
                target = "topic" if round_number == 1 else personas[index - 1]["name"]
                dialogues.append({
                    "speaker": speaker,
                    "role": persona["role"],
                    "reply_to": target,
                    "round": round_number,
                    "stance": "challenge" if round_number < 3 else "compromise",
                    "claim_reference": "현재 요구사항" if round_number == 1 else f"{target}의 이전 주장",
                    "content": f"{target}의 주장을 검토해 조건과 실패 대응을 수정하겠습니다.",
                })
            risks = []
            if round_number == 3:
                risks = [{
                    "title": "부분 실패 재처리 위험",
                    "description": "취소와 환불의 상태 전이가 어긋날 수 있습니다.",
                    "related_requirement": "주문 취소",
                    "raised_by": "강혜원",
                    "participants": ["김도윤", "강혜원"],
                }]
            return json.dumps({"dialogues": dialogues, "risks": risks}, ensure_ascii=False)

    stub_llm = StubLlm()
    monkeypatch.setattr(simulation, "get_llm_service", lambda: stub_llm)
    state = {"derived_risks": []}

    dialogues = await simulation._build_live_dialogues(
        personas,
        {
            "product_name": "주문 지원 AI",
            "problem": "고객 문의를 빠르게 처리하지 못합니다.",
            "solution": "정책 기반 주문 지원",
            "requirements": ["주문 취소"],
        },
        session_state=state,
    )

    assert stub_llm.calls == 3
    assert len(dialogues) == 9
    assert all(dialogue["reply_to"] == "topic" for dialogue in dialogues[:3])
    assert all(dialogue["reply_to"] != "topic" for dialogue in dialogues[3:])
    assert all(dialogue["claim_reference"] for dialogue in dialogues)
    assert state["derived_risks"] == [{
        "title": "부분 실패 재처리 위험",
        "description": "취소와 환불의 상태 전이가 어긋날 수 있습니다.",
        "related_requirement": "주문 취소",
        "raised_by": "강혜원",
        "participants": ["김도윤", "강혜원"],
        "emerges_after": 7,
    }]
