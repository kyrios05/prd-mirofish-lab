"""
tests/test_chat_api.py — Integration tests for the Chat API (T03).

Test groups
-----------
  1. TestSessionCreate       – POST /chat/sessions
  2. TestSessionStatus       – GET  /chat/sessions/{session_id}
  3. TestChatMessageContract – POST /chat/message (request/response shape)
  4. TestMockPRDProgression  – Multi-turn PRD fill + completeness growth
  5. TestDraftStatusTransitions – empty → incomplete → ready_for_validation
  6. TestStructuredPRDOutput – structured_prd field presence and content
  7. TestNotFoundHandling    – 404 for unknown session_id (both endpoints)

All tests use FastAPI TestClient (httpx transport) — no actual HTTP server.
The in-memory session_store is cleared between tests via the autouse fixture.

Scope guard: no LLM calls, no DB, no renderer, no MiroFish.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.session_store import session_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_store():
    """Wipe the in-memory session store before (and after) every test."""
    session_store.clear()
    yield
    session_store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def session_id(client: TestClient) -> str:
    """Create a session and return its session_id."""
    resp = client.post("/chat/sessions")
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# 1. TestSessionCreate
# ---------------------------------------------------------------------------

class TestSessionCreate:
    def test_create_session_returns_201(self, client: TestClient):
        resp = client.post("/chat/sessions")
        assert resp.status_code == 201

    def test_create_session_response_shape(self, client: TestClient):
        resp = client.post("/chat/sessions")
        data = resp.json()
        assert "session_id" in data
        assert "created_at" in data
        assert "message" in data

    def test_session_id_is_nonempty_string(self, client: TestClient):
        resp = client.post("/chat/sessions")
        assert isinstance(resp.json()["session_id"], str)
        assert len(resp.json()["session_id"]) > 0

    def test_two_sessions_have_different_ids(self, client: TestClient):
        id1 = client.post("/chat/sessions").json()["session_id"]
        id2 = client.post("/chat/sessions").json()["session_id"]
        assert id1 != id2

    def test_created_at_is_iso8601(self, client: TestClient):
        from datetime import datetime
        created_at = client.post("/chat/sessions").json()["created_at"]
        # Should parse without error
        datetime.fromisoformat(created_at)


# ---------------------------------------------------------------------------
# 2. TestSessionStatus
# ---------------------------------------------------------------------------

class TestSessionStatus:
    def test_get_fresh_session_returns_200(self, client: TestClient, session_id: str):
        resp = client.get(f"/chat/sessions/{session_id}")
        assert resp.status_code == 200

    def test_fresh_session_has_zero_turns(self, client: TestClient, session_id: str):
        data = client.get(f"/chat/sessions/{session_id}").json()
        assert data["turn_count"] == 0

    def test_fresh_session_has_no_prd_draft(self, client: TestClient, session_id: str):
        data = client.get(f"/chat/sessions/{session_id}").json()
        assert data["has_prd_draft"] is False

    def test_fresh_session_draft_status_is_empty(self, client: TestClient, session_id: str):
        data = client.get(f"/chat/sessions/{session_id}").json()
        assert data["draft_status"] == "empty"

    def test_fresh_session_completeness_structure(self, client: TestClient, session_id: str):
        data = client.get(f"/chat/sessions/{session_id}").json()
        c = data["completeness"]
        assert "filled" in c
        assert "missing" in c
        assert "progress" in c
        assert c["progress"] == 0.0
        assert len(c["missing"]) == 13  # 13 content sections

    def test_fresh_session_empty_history(self, client: TestClient, session_id: str):
        data = client.get(f"/chat/sessions/{session_id}").json()
        assert data["conversation_history"] == []

    def test_session_status_404_unknown(self, client: TestClient):
        resp = client.get("/chat/sessions/does-not-exist-xyz")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. TestChatMessageContract
# ---------------------------------------------------------------------------

class TestChatMessageContract:
    def test_send_message_returns_200(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "안녕하세요!"},
        )
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "테스트 메시지"},
        )
        data = resp.json()
        assert "session_id" in data
        assert "assistant_message" in data
        assert "structured_prd" in data
        assert "draft_status" in data
        assert "completeness" in data
        assert "next_questions" in data

    def test_session_id_echoed(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert resp.json()["session_id"] == session_id

    def test_assistant_message_is_nonempty(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert len(resp.json()["assistant_message"]) > 0

    def test_completeness_has_correct_sub_fields(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        c = resp.json()["completeness"]
        assert "filled" in c
        assert "missing" in c
        assert "progress" in c

    def test_next_questions_is_list(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert isinstance(resp.json()["next_questions"], list)

    def test_optional_context_accepted(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={
                "session_id": session_id,
                "message": "hello",
                "context": {"hint": "mobile app"},
            },
        )
        assert resp.status_code == 200

    def test_unknown_session_returns_404(self, client: TestClient):
        resp = client.post(
            "/chat/message",
            json={"session_id": "non-existent-session", "message": "hi"},
        )
        assert resp.status_code == 404

    def test_empty_message_rejected(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": ""},
        )
        assert resp.status_code == 422  # Pydantic min_length=1 validation


# ---------------------------------------------------------------------------
# 4. TestMockPRDProgression
# ---------------------------------------------------------------------------

class TestMockPRDProgression:
    def _send(self, client: TestClient, session_id: str, msg: str = "넥스트") -> dict:
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": msg},
        )
        assert resp.status_code == 200
        return resp.json()

    def test_turn1_fills_metadata_and_product(self, client: TestClient, session_id: str):
        data = self._send(client, session_id)
        prd = data["structured_prd"]
        assert prd is not None
        assert "metadata" in prd
        assert "product" in prd

    def test_turn2_fills_users_and_problem(self, client: TestClient, session_id: str):
        self._send(client, session_id)          # turn 1
        data = self._send(client, session_id)   # turn 2
        prd = data["structured_prd"]
        assert "users" in prd
        assert "problem" in prd

    def test_turn3_fills_solution_and_scope(self, client: TestClient, session_id: str):
        for _ in range(2):
            self._send(client, session_id)
        data = self._send(client, session_id)   # turn 3
        prd = data["structured_prd"]
        assert "solution" in prd
        assert "scope" in prd

    def test_turn4_fills_requirements_and_success_metrics(self, client: TestClient, session_id: str):
        for _ in range(3):
            self._send(client, session_id)
        data = self._send(client, session_id)   # turn 4
        prd = data["structured_prd"]
        assert "requirements" in prd
        assert "success_metrics" in prd

    def test_turn5_completes_all_sections(self, client: TestClient, session_id: str):
        for _ in range(4):
            self._send(client, session_id)
        data = self._send(client, session_id)   # turn 5
        prd = data["structured_prd"]
        required_sections = [
            "metadata", "product", "users", "problem", "solution", "scope",
            "requirements", "success_metrics", "delivery", "assumptions",
            "risks", "open_questions", "validation",
        ]
        for section in required_sections:
            assert section in prd, f"Section '{section}' missing after turn 5"

    def test_turn_count_increments_in_session_status(self, client: TestClient, session_id: str):
        for i in range(3):
            self._send(client, session_id)
        status = client.get(f"/chat/sessions/{session_id}").json()
        assert status["turn_count"] == 3

    def test_session_history_grows_with_turns(self, client: TestClient, session_id: str):
        for _ in range(2):
            self._send(client, session_id)
        status = client.get(f"/chat/sessions/{session_id}").json()
        # Each turn adds one user + one assistant message
        assert len(status["conversation_history"]) == 4

    def test_turn6_returns_fallback_message(self, client: TestClient, session_id: str):
        for _ in range(5):
            self._send(client, session_id)
        data = self._send(client, session_id)   # turn 6
        # Should still return 200 with fallback assistant message
        assert len(data["assistant_message"]) > 0


# ---------------------------------------------------------------------------
# 5. TestDraftStatusTransitions
# ---------------------------------------------------------------------------

class TestDraftStatusTransitions:
    def _send(self, client: TestClient, session_id: str) -> dict:
        return client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "계속"},
        ).json()

    def test_draft_status_empty_before_any_message(self, client: TestClient, session_id: str):
        status = client.get(f"/chat/sessions/{session_id}").json()
        assert status["draft_status"] == "empty"

    def test_draft_status_incomplete_after_turn1(self, client: TestClient, session_id: str):
        data = self._send(client, session_id)
        assert data["draft_status"] == "incomplete"

    def test_draft_status_incomplete_after_turn4(self, client: TestClient, session_id: str):
        for _ in range(4):
            data = self._send(client, session_id)
        assert data["draft_status"] == "incomplete"

    def test_draft_status_ready_after_turn5(self, client: TestClient, session_id: str):
        for _ in range(5):
            data = self._send(client, session_id)
        assert data["draft_status"] == "ready_for_validation"

    def test_session_status_reflects_ready_status(self, client: TestClient, session_id: str):
        for _ in range(5):
            self._send(client, session_id)
        status = client.get(f"/chat/sessions/{session_id}").json()
        assert status["draft_status"] == "ready_for_validation"


# ---------------------------------------------------------------------------
# 6. TestStructuredPRDOutput
# ---------------------------------------------------------------------------

class TestStructuredPRDOutput:
    def _send_n(self, client: TestClient, session_id: str, n: int) -> dict:
        data = {}
        for _ in range(n):
            resp = client.post(
                "/chat/message",
                json={"session_id": session_id, "message": "계속"},
            )
            data = resp.json()
        return data

    def test_structured_prd_is_none_before_first_turn(self, client: TestClient, session_id: str):
        status = client.get(f"/chat/sessions/{session_id}").json()
        assert status["has_prd_draft"] is False

    def test_structured_prd_has_schema_version(self, client: TestClient, session_id: str):
        data = self._send_n(client, session_id, 1)
        prd = data["structured_prd"]
        assert prd.get("schema_version") == "0.1.0"

    def test_full_prd_metadata_has_project_id(self, client: TestClient, session_id: str):
        data = self._send_n(client, session_id, 1)
        metadata = data["structured_prd"]["metadata"]
        assert metadata["project_id"].startswith("proj-")

    def test_full_prd_product_has_required_fields(self, client: TestClient, session_id: str):
        data = self._send_n(client, session_id, 1)
        product = data["structured_prd"]["product"]
        assert "name" in product
        assert "one_liner" in product
        assert "platforms" in product

    def test_completeness_progress_increases_each_turn(self, client: TestClient, session_id: str):
        prev_progress = 0.0
        for _ in range(5):
            resp = client.post(
                "/chat/message",
                json={"session_id": session_id, "message": "다음"},
            )
            progress = resp.json()["completeness"]["progress"]
            assert progress >= prev_progress
            prev_progress = progress

    def test_completeness_progress_is_1_after_turn5(self, client: TestClient, session_id: str):
        data = self._send_n(client, session_id, 5)
        assert data["completeness"]["progress"] == 1.0

    def test_completeness_missing_shrinks_with_turns(self, client: TestClient, session_id: str):
        prev_missing_count = 13
        for _ in range(5):
            resp = client.post(
                "/chat/message",
                json={"session_id": session_id, "message": "다음"},
            )
            missing_count = len(resp.json()["completeness"]["missing"])
            assert missing_count <= prev_missing_count
            prev_missing_count = missing_count

    def test_full_prd_product_industry_context_is_list(self, client: TestClient, session_id: str):
        """industry_context must be list[str] per T01 fix."""
        data = self._send_n(client, session_id, 1)
        industry_context = data["structured_prd"]["product"].get("industry_context")
        assert industry_context is None or isinstance(industry_context, list)

    def test_full_prd_scope_launch_constraints_is_list(self, client: TestClient, session_id: str):
        """launch_constraints must be list[str] per T01 fix."""
        data = self._send_n(client, session_id, 3)
        constraints = data["structured_prd"]["scope"].get("launch_constraints")
        assert constraints is None or isinstance(constraints, list)

    def test_full_prd_solution_user_journey_is_list(self, client: TestClient, session_id: str):
        """user_journey must be list[str] per T01 fix."""
        data = self._send_n(client, session_id, 3)
        user_journey = data["structured_prd"]["solution"].get("user_journey")
        assert user_journey is None or isinstance(user_journey, list)


# ---------------------------------------------------------------------------
# 7. TestNotFoundHandling
# ---------------------------------------------------------------------------

class TestNotFoundHandling:
    def test_message_to_unknown_session_404(self, client: TestClient):
        resp = client.post(
            "/chat/message",
            json={"session_id": "aaaaaaaa-0000-0000-0000-000000000000", "message": "hi"},
        )
        assert resp.status_code == 404

    def test_status_of_unknown_session_404(self, client: TestClient):
        resp = client.get("/chat/sessions/aaaaaaaa-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_404_response_has_detail_field(self, client: TestClient):
        resp = client.get("/chat/sessions/totally-unknown")
        assert "detail" in resp.json()

    def test_deleted_session_gives_404_on_status(self, client: TestClient, session_id: str):
        # Confirm session exists first
        assert client.get(f"/chat/sessions/{session_id}").status_code == 200
        # Manually delete from store
        session_store.delete_session(session_id)
        assert client.get(f"/chat/sessions/{session_id}").status_code == 404
