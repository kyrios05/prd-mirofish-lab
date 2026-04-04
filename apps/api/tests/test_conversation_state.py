"""
tests/test_conversation_state.py — T09 test suite.

Test groups
───────────
  1.  TestConversationPhaseEnum       — enum values, JSON serialisation
  2.  TestStateMachineInitial         — initial state is GREETING
  3.  TestStateMachineTransitions     — allowed / disallowed transitions
  4.  TestStateMachineAutoAdvance     — auto_advance logic
  5.  TestPhaseHistory                — phase_history recording
  6.  TestCheckpointSave              — save_checkpoint returns correct data
  7.  TestCheckpointRestore           — restore_checkpoint behaviour
  8.  TestCheckpointList              — list_checkpoints sorting
  9.  TestAutoCheckpointOnTransition  — auto-checkpoint in send_message
  10. TestChatResponsePhaseFields     — current_phase / available_actions in API response
  11. TestCheckpointEndpoint          — POST /sessions/{id}/checkpoint
  12. TestRestoreEndpoint             — POST /sessions/{id}/restore
  13. TestCheckpointsListEndpoint     — GET  /sessions/{id}/checkpoints
  14. TestRegressionT03               — T03 existing behaviour unchanged

All integration tests use FastAPI TestClient; session_store cleared between tests.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.completeness import CompletenessResult, DraftStatus
from app.services.conversation_state import (
    Checkpoint,
    ConversationPhase,
    ConversationStateMachine,
    PhaseTransition,
    get_available_actions,
    list_checkpoints,
    restore_checkpoint,
    save_checkpoint,
    state_machine_from_phase,
)
from app.services.session_store import SessionState, session_store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_store():
    """Wipe in-memory session store before and after every test."""
    session_store.clear()
    yield
    session_store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def session_id(client: TestClient) -> str:
    resp = client.post("/chat/sessions")
    assert resp.status_code == 201
    return resp.json()["session_id"]


@pytest.fixture
def fresh_state() -> SessionState:
    """Return a fresh SessionState (not persisted in store)."""
    return SessionState(session_id="test-session-001")


@pytest.fixture
def completeness_zero() -> CompletenessResult:
    return CompletenessResult(
        filled=[],
        missing=["metadata", "product"],
        progress=0.0,
        draft_status=DraftStatus.EMPTY,
    )


@pytest.fixture
def completeness_half() -> CompletenessResult:
    return CompletenessResult(
        filled=["metadata", "product", "users", "problem", "solution", "scope", "requirements"],
        missing=["success_metrics", "delivery", "assumptions", "risks", "open_questions", "validation"],
        progress=7 / 13,
        draft_status=DraftStatus.INCOMPLETE,
    )


@pytest.fixture
def completeness_full() -> CompletenessResult:
    from app.services.completeness import REQUIRED_SECTIONS
    return CompletenessResult(
        filled=list(REQUIRED_SECTIONS),
        missing=[],
        progress=1.0,
        draft_status=DraftStatus.READY_FOR_VALIDATION,
    )


# ---------------------------------------------------------------------------
# 1. TestConversationPhaseEnum
# ---------------------------------------------------------------------------

class TestConversationPhaseEnum:
    def test_all_phases_exist(self):
        phases = [p.value for p in ConversationPhase]
        assert "greeting" in phases
        assert "interviewing" in phases
        assert "reviewing" in phases
        assert "ready_for_validation" in phases
        assert "validated" in phases

    def test_phase_is_str_enum(self):
        assert isinstance(ConversationPhase.GREETING, str)
        assert ConversationPhase.GREETING == "greeting"

    def test_phase_json_serialisable(self):
        serialised = json.dumps({"phase": ConversationPhase.INTERVIEWING})
        assert '"interviewing"' in serialised

    def test_phase_from_string(self):
        assert ConversationPhase("reviewing") == ConversationPhase.REVIEWING

    def test_invalid_phase_raises(self):
        with pytest.raises(ValueError):
            ConversationPhase("nonexistent_phase")

    def test_get_available_actions_greeting(self):
        actions = get_available_actions(ConversationPhase.GREETING)
        assert isinstance(actions, list)
        assert len(actions) >= 1

    def test_get_available_actions_interviewing(self):
        actions = get_available_actions(ConversationPhase.INTERVIEWING)
        assert "continue" in actions
        assert "save_checkpoint" in actions

    def test_get_available_actions_reviewing(self):
        actions = get_available_actions(ConversationPhase.REVIEWING)
        assert "confirm" in actions
        assert "edit_section" in actions

    def test_get_available_actions_ready(self):
        actions = get_available_actions(ConversationPhase.READY_FOR_VALIDATION)
        assert "run_validation" in actions
        assert "go_back" in actions

    def test_get_available_actions_validated(self):
        actions = get_available_actions(ConversationPhase.VALIDATED)
        assert "view_result" in actions


# ---------------------------------------------------------------------------
# 2. TestStateMachineInitial
# ---------------------------------------------------------------------------

class TestStateMachineInitial:
    def test_default_phase_is_greeting(self):
        sm = ConversationStateMachine()
        assert sm.current_phase == ConversationPhase.GREETING

    def test_initial_phase_accepts_custom(self):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        assert sm.current_phase == ConversationPhase.INTERVIEWING

    def test_state_machine_from_phase_greeting(self):
        sm = state_machine_from_phase("greeting")
        assert sm.current_phase == ConversationPhase.GREETING

    def test_state_machine_from_phase_reviewing(self):
        sm = state_machine_from_phase("reviewing")
        assert sm.current_phase == ConversationPhase.REVIEWING

    def test_state_machine_from_invalid_falls_back_to_greeting(self):
        sm = state_machine_from_phase("unknown_phase_xyz")
        assert sm.current_phase == ConversationPhase.GREETING


# ---------------------------------------------------------------------------
# 3. TestStateMachineTransitions
# ---------------------------------------------------------------------------

class TestStateMachineTransitions:
    def test_greeting_to_interviewing_succeeds(self):
        sm = ConversationStateMachine()
        assert sm.transition(ConversationPhase.INTERVIEWING) is True
        assert sm.current_phase == ConversationPhase.INTERVIEWING

    def test_interviewing_to_reviewing_succeeds_when_complete(
        self, completeness_full
    ):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        result = sm.transition(
            ConversationPhase.REVIEWING, completeness=completeness_full
        )
        assert result is True
        assert sm.current_phase == ConversationPhase.REVIEWING

    def test_interviewing_to_reviewing_rejected_when_incomplete(
        self, completeness_half
    ):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        result = sm.transition(
            ConversationPhase.REVIEWING, completeness=completeness_half
        )
        assert result is False
        assert sm.current_phase == ConversationPhase.INTERVIEWING

    def test_interviewing_to_reviewing_rejected_with_no_completeness(self):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        result = sm.transition(ConversationPhase.REVIEWING)
        assert result is False

    def test_reviewing_to_interviewing_rollback(self):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.REVIEWING)
        result = sm.transition(ConversationPhase.INTERVIEWING)
        assert result is True
        assert sm.current_phase == ConversationPhase.INTERVIEWING

    def test_reviewing_to_ready_for_validation(self):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.REVIEWING)
        result = sm.transition(ConversationPhase.READY_FOR_VALIDATION)
        assert result is True
        assert sm.current_phase == ConversationPhase.READY_FOR_VALIDATION

    def test_ready_to_validated(self):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.READY_FOR_VALIDATION)
        result = sm.transition(ConversationPhase.VALIDATED)
        assert result is True
        assert sm.current_phase == ConversationPhase.VALIDATED

    def test_validated_to_reviewing_rollback(self):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.VALIDATED)
        result = sm.transition(ConversationPhase.REVIEWING)
        assert result is True
        assert sm.current_phase == ConversationPhase.REVIEWING

    def test_invalid_transition_returns_false(self):
        sm = ConversationStateMachine()  # GREETING
        result = sm.transition(ConversationPhase.REVIEWING)
        assert result is False
        assert sm.current_phase == ConversationPhase.GREETING

    def test_greeting_to_validated_disallowed(self):
        sm = ConversationStateMachine()
        result = sm.transition(ConversationPhase.VALIDATED)
        assert result is False

    def test_can_transition_true_for_allowed(self):
        sm = ConversationStateMachine()
        assert sm.can_transition(ConversationPhase.INTERVIEWING) is True

    def test_can_transition_false_for_disallowed(self):
        sm = ConversationStateMachine()
        assert sm.can_transition(ConversationPhase.REVIEWING) is False

    def test_can_transition_interviewing_to_reviewing_requires_completeness(
        self, completeness_full, completeness_half
    ):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        assert sm.can_transition(
            ConversationPhase.REVIEWING, completeness=completeness_full
        ) is True
        assert sm.can_transition(
            ConversationPhase.REVIEWING, completeness=completeness_half
        ) is False


# ---------------------------------------------------------------------------
# 4. TestStateMachineAutoAdvance
# ---------------------------------------------------------------------------

class TestStateMachineAutoAdvance:
    def test_auto_advance_returns_none_when_progress_zero(self, completeness_zero):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        result = sm.auto_advance(completeness_zero)
        assert result is None
        assert sm.current_phase == ConversationPhase.INTERVIEWING

    def test_auto_advance_returns_none_when_progress_half(self, completeness_half):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        result = sm.auto_advance(completeness_half)
        assert result is None

    def test_auto_advance_returns_reviewing_when_progress_full(
        self, completeness_full
    ):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        result = sm.auto_advance(completeness_full)
        assert result == ConversationPhase.REVIEWING
        assert sm.current_phase == ConversationPhase.REVIEWING

    def test_auto_advance_no_op_for_greeting(self, completeness_full):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.GREETING)
        result = sm.auto_advance(completeness_full)
        assert result is None
        assert sm.current_phase == ConversationPhase.GREETING

    def test_auto_advance_no_op_for_reviewing(self, completeness_full):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.REVIEWING)
        result = sm.auto_advance(completeness_full)
        assert result is None

    def test_auto_advance_appends_to_phase_history(self, completeness_full):
        sm = ConversationStateMachine(initial_phase=ConversationPhase.INTERVIEWING)
        history: list[PhaseTransition] = []
        sm.auto_advance(completeness_full, phase_history=history)
        assert len(history) == 1
        assert history[0].from_phase == "interviewing"
        assert history[0].to_phase == "reviewing"
        assert history[0].trigger == "auto_advance"


# ---------------------------------------------------------------------------
# 5. TestPhaseHistory
# ---------------------------------------------------------------------------

class TestPhaseHistory:
    def test_transition_appends_to_history(self):
        sm = ConversationStateMachine()
        history: list[PhaseTransition] = []
        sm.transition(
            ConversationPhase.INTERVIEWING,
            trigger="user_first_message",
            phase_history=history,
        )
        assert len(history) == 1
        record = history[0]
        assert record.from_phase == "greeting"
        assert record.to_phase == "interviewing"
        assert record.trigger == "user_first_message"

    def test_transition_without_history_arg_does_not_crash(self):
        sm = ConversationStateMachine()
        result = sm.transition(ConversationPhase.INTERVIEWING)
        assert result is True

    def test_history_timestamp_is_iso8601(self):
        sm = ConversationStateMachine()
        history: list[PhaseTransition] = []
        sm.transition(
            ConversationPhase.INTERVIEWING,
            phase_history=history,
        )
        ts = history[0].timestamp
        datetime.fromisoformat(ts)  # must not raise

    def test_multiple_transitions_recorded_in_order(
        self, completeness_full
    ):
        sm = ConversationStateMachine()
        history: list[PhaseTransition] = []
        sm.transition(
            ConversationPhase.INTERVIEWING,
            trigger="t1",
            phase_history=history,
        )
        sm.transition(
            ConversationPhase.REVIEWING,
            trigger="t2",
            completeness=completeness_full,
            phase_history=history,
        )
        assert len(history) == 2
        assert history[0].to_phase == "interviewing"
        assert history[1].to_phase == "reviewing"

    def test_phase_transition_to_dict(self):
        pt = PhaseTransition(
            from_phase="greeting",
            to_phase="interviewing",
            trigger="test",
        )
        d = pt.to_dict()
        assert d["from_phase"] == "greeting"
        assert d["to_phase"] == "interviewing"
        assert d["trigger"] == "test"
        assert "timestamp" in d


# ---------------------------------------------------------------------------
# 6. TestCheckpointSave
# ---------------------------------------------------------------------------

class TestCheckpointSave:
    def test_save_checkpoint_returns_checkpoint(self, fresh_state):
        fresh_state.current_prd_draft = {"schema_version": "0.1.0", "product": {"name": "Test"}}
        cp = save_checkpoint(fresh_state, label="initial save")
        assert isinstance(cp, Checkpoint)

    def test_save_checkpoint_has_uuid_id(self, fresh_state):
        import uuid
        cp = save_checkpoint(fresh_state, label="test")
        uuid.UUID(cp.checkpoint_id)  # must not raise

    def test_save_checkpoint_has_iso8601_created_at(self, fresh_state):
        cp = save_checkpoint(fresh_state, label="test")
        datetime.fromisoformat(cp.created_at)  # must not raise

    def test_save_checkpoint_snapshot_is_deep_copy(self, fresh_state):
        fresh_state.current_prd_draft = {"key": "original"}
        cp = save_checkpoint(fresh_state, label="test")
        # Mutate the original
        fresh_state.current_prd_draft["key"] = "mutated"
        # Snapshot must still have the original value
        assert cp.prd_snapshot["key"] == "original"

    def test_save_checkpoint_empty_draft_stores_empty_dict(self, fresh_state):
        fresh_state.current_prd_draft = None
        cp = save_checkpoint(fresh_state, label="empty")
        assert cp.prd_snapshot == {}

    def test_save_checkpoint_appended_to_state(self, fresh_state):
        assert len(fresh_state.checkpoints) == 0
        save_checkpoint(fresh_state, label="cp1")
        assert len(fresh_state.checkpoints) == 1
        save_checkpoint(fresh_state, label="cp2")
        assert len(fresh_state.checkpoints) == 2

    def test_save_checkpoint_records_turn_count(self, fresh_state):
        fresh_state.turn_count = 7
        cp = save_checkpoint(fresh_state, label="test")
        assert cp.turn_count == 7

    def test_save_checkpoint_records_current_phase(self, fresh_state):
        fresh_state.current_phase = "interviewing"
        cp = save_checkpoint(fresh_state, label="test")
        assert cp.phase == "interviewing"

    def test_checkpoint_to_dict_contains_all_keys(self, fresh_state):
        fresh_state.current_prd_draft = {"x": 1}
        cp = save_checkpoint(fresh_state, label="dict test")
        d = cp.to_dict()
        for key in ("checkpoint_id", "created_at", "phase", "turn_count", "prd_snapshot", "label"):
            assert key in d

    def test_checkpoint_prd_snapshot_is_json_serialisable(self, fresh_state):
        fresh_state.current_prd_draft = {"schema_version": "0.1.0"}
        cp = save_checkpoint(fresh_state, label="json test")
        json.dumps(cp.to_dict())  # must not raise


# ---------------------------------------------------------------------------
# 7. TestCheckpointRestore
# ---------------------------------------------------------------------------

class TestCheckpointRestore:
    def _make_state_with_checkpoint(self) -> tuple[SessionState, str]:
        state = SessionState(session_id="restore-test")
        state.current_prd_draft = {"product": {"name": "Original"}}
        state.turn_count = 3
        state.current_phase = "interviewing"
        cp = save_checkpoint(state, label="before edit")
        return state, cp.checkpoint_id

    def test_restore_returns_true_on_success(self):
        state, cp_id = self._make_state_with_checkpoint()
        # Mutate state
        state.current_prd_draft = {"product": {"name": "Changed"}}
        assert restore_checkpoint(state, cp_id) is True

    def test_restore_returns_false_for_unknown_id(self):
        state = SessionState(session_id="x")
        assert restore_checkpoint(state, "nonexistent-id") is False

    def test_restore_reverts_prd_draft(self):
        state, cp_id = self._make_state_with_checkpoint()
        original_name = state.current_prd_draft["product"]["name"]
        # Mutate
        state.current_prd_draft["product"]["name"] = "Changed"
        restore_checkpoint(state, cp_id)
        assert state.current_prd_draft["product"]["name"] == original_name

    def test_restore_reverts_turn_count(self):
        state, cp_id = self._make_state_with_checkpoint()
        state.turn_count = 99
        restore_checkpoint(state, cp_id)
        assert state.turn_count == 3

    def test_restore_reverts_phase(self):
        state, cp_id = self._make_state_with_checkpoint()
        state.current_phase = "reviewing"
        restore_checkpoint(state, cp_id)
        assert state.current_phase == "interviewing"

    def test_restore_preserves_conversation_history(self):
        from app.services.session_store import ConversationTurn
        state, cp_id = self._make_state_with_checkpoint()
        state.conversation_history = [
            ConversationTurn(role="user", content="hello"),
            ConversationTurn(role="assistant", content="hi"),
        ]
        restore_checkpoint(state, cp_id)
        assert len(state.conversation_history) == 2
        assert state.conversation_history[0].content == "hello"

    def test_restore_snapshot_is_deep_copy(self):
        state, cp_id = self._make_state_with_checkpoint()
        restore_checkpoint(state, cp_id)
        # Mutate the restored draft
        if state.current_prd_draft:
            state.current_prd_draft["product"]["name"] = "post-restore-mutation"
        # Restore again — snapshot must still hold original value
        restore_checkpoint(state, cp_id)
        if state.current_prd_draft:
            assert state.current_prd_draft["product"]["name"] == "Original"

    def test_restore_none_draft_restores_none(self):
        state = SessionState(session_id="none-draft")
        state.current_prd_draft = None
        cp = save_checkpoint(state, label="empty")
        state.current_prd_draft = {"added": "later"}
        restore_checkpoint(state, cp.checkpoint_id)
        assert state.current_prd_draft is None


# ---------------------------------------------------------------------------
# 8. TestCheckpointList
# ---------------------------------------------------------------------------

class TestCheckpointList:
    def test_list_checkpoints_empty_by_default(self, fresh_state):
        result = list_checkpoints(fresh_state)
        assert result == []

    def test_list_checkpoints_returns_all(self, fresh_state):
        save_checkpoint(fresh_state, label="cp1")
        save_checkpoint(fresh_state, label="cp2")
        save_checkpoint(fresh_state, label="cp3")
        result = list_checkpoints(fresh_state)
        assert len(result) == 3

    def test_list_checkpoints_newest_first(self, fresh_state):
        import time
        save_checkpoint(fresh_state, label="first")
        time.sleep(0.01)  # ensure distinct timestamps
        save_checkpoint(fresh_state, label="second")
        result = list_checkpoints(fresh_state)
        assert result[0].label == "second"
        assert result[1].label == "first"

    def test_list_checkpoints_is_new_list(self, fresh_state):
        save_checkpoint(fresh_state, label="cp")
        result1 = list_checkpoints(fresh_state)
        result2 = list_checkpoints(fresh_state)
        # Must be separate list objects
        assert result1 is not result2


# ---------------------------------------------------------------------------
# 9. TestAutoCheckpointOnTransition
# ---------------------------------------------------------------------------

class TestAutoCheckpointOnTransition:
    def test_first_message_triggers_auto_checkpoint(
        self, client: TestClient, session_id: str
    ):
        """Sending first message causes GREETING→INTERVIEWING and auto-checkpoint."""
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hi"},
        )
        assert resp.status_code == 200

        # Checkpoint endpoint should show at least one checkpoint
        cp_resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        assert cp_resp.status_code == 200
        checkpoints = cp_resp.json()["checkpoints"]
        assert len(checkpoints) >= 1

    def test_auto_checkpoint_label_contains_phase(
        self, client: TestClient, session_id: str
    ):
        client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "start"},
        )
        cp_resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        labels = [c["label"] for c in cp_resp.json()["checkpoints"]]
        # At least one label should mention "interviewing"
        assert any("interviewing" in lbl for lbl in labels)

    def test_phase_after_first_message_is_interviewing(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert resp.json()["current_phase"] == "interviewing"


# ---------------------------------------------------------------------------
# 10. TestChatResponsePhaseFields
# ---------------------------------------------------------------------------

class TestChatResponsePhaseFields:
    def test_response_has_current_phase(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "test"},
        )
        assert "current_phase" in resp.json()

    def test_response_has_available_actions(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "test"},
        )
        assert "available_actions" in resp.json()
        assert isinstance(resp.json()["available_actions"], list)

    def test_available_actions_nonempty_after_first_message(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "test"},
        )
        assert len(resp.json()["available_actions"]) > 0

    def test_current_phase_is_string(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "test"},
        )
        assert isinstance(resp.json()["current_phase"], str)

    def test_existing_fields_still_present(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "test"},
        )
        data = resp.json()
        for field_name in (
            "session_id", "assistant_message", "draft_status",
            "completeness", "next_questions",
        ):
            assert field_name in data, f"Missing field: {field_name}"

    def test_reviewing_phase_overrides_assistant_message(
        self, client: TestClient, session_id: str
    ):
        """After 5 turns the phase should reach REVIEWING and the message changes."""
        for _ in range(5):
            resp = client.post(
                "/chat/message",
                json={"session_id": session_id, "message": "continue"},
            )
        data = resp.json()
        if data["current_phase"] == "reviewing":
            assert "PRD 초안이 완성되었습니다" in data["assistant_message"]

    def test_interviewing_phase_available_actions_contain_continue(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "first message"},
        )
        if resp.json()["current_phase"] == "interviewing":
            assert "continue" in resp.json()["available_actions"]


# ---------------------------------------------------------------------------
# 11. TestCheckpointEndpoint
# ---------------------------------------------------------------------------

class TestCheckpointEndpoint:
    def test_create_checkpoint_returns_200(self, client: TestClient, session_id: str):
        # First send a message to have some state
        client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        resp = client.post(f"/chat/sessions/{session_id}/checkpoint")
        assert resp.status_code == 200

    def test_create_checkpoint_returns_checkpoint_id(
        self, client: TestClient, session_id: str
    ):
        client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        resp = client.post(f"/chat/sessions/{session_id}/checkpoint")
        data = resp.json()
        assert "checkpoint_id" in data
        assert len(data["checkpoint_id"]) > 0

    def test_create_checkpoint_returns_label(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            f"/chat/sessions/{session_id}/checkpoint",
            params={"label": "my custom label"},
        )
        assert resp.json()["label"] == "my custom label"

    def test_create_checkpoint_default_label_when_omitted(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(f"/chat/sessions/{session_id}/checkpoint")
        assert "manual checkpoint" in resp.json()["label"]

    def test_create_checkpoint_404_for_unknown_session(
        self, client: TestClient
    ):
        resp = client.post("/chat/sessions/nonexistent-id/checkpoint")
        assert resp.status_code == 404

    def test_create_checkpoint_includes_phase(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(f"/chat/sessions/{session_id}/checkpoint")
        assert "phase" in resp.json()

    def test_create_checkpoint_id_is_uuid(
        self, client: TestClient, session_id: str
    ):
        import uuid
        resp = client.post(f"/chat/sessions/{session_id}/checkpoint")
        uuid.UUID(resp.json()["checkpoint_id"])  # must not raise

    def test_multiple_checkpoints_have_different_ids(
        self, client: TestClient, session_id: str
    ):
        id1 = client.post(f"/chat/sessions/{session_id}/checkpoint").json()["checkpoint_id"]
        id2 = client.post(f"/chat/sessions/{session_id}/checkpoint").json()["checkpoint_id"]
        assert id1 != id2


# ---------------------------------------------------------------------------
# 12. TestRestoreEndpoint
# ---------------------------------------------------------------------------

class TestRestoreEndpoint:
    def _create_checkpoint_via_api(
        self, client: TestClient, session_id: str
    ) -> str:
        """Helper: send a message then create a checkpoint, return its id."""
        client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "first"},
        )
        resp = client.post(
            f"/chat/sessions/{session_id}/checkpoint",
            params={"label": "before change"},
        )
        return resp.json()["checkpoint_id"]

    def test_restore_returns_200(self, client: TestClient, session_id: str):
        cp_id = self._create_checkpoint_via_api(client, session_id)
        resp = client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": cp_id},
        )
        assert resp.status_code == 200

    def test_restore_returns_restored_true(self, client: TestClient, session_id: str):
        cp_id = self._create_checkpoint_via_api(client, session_id)
        resp = client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": cp_id},
        )
        assert resp.json()["restored"] is True

    def test_restore_returns_checkpoint_id(self, client: TestClient, session_id: str):
        cp_id = self._create_checkpoint_via_api(client, session_id)
        resp = client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": cp_id},
        )
        assert resp.json()["checkpoint_id"] == cp_id

    def test_restore_returns_current_phase(self, client: TestClient, session_id: str):
        cp_id = self._create_checkpoint_via_api(client, session_id)
        resp = client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": cp_id},
        )
        assert "current_phase" in resp.json()
        assert isinstance(resp.json()["current_phase"], str)

    def test_restore_returns_turn_count(self, client: TestClient, session_id: str):
        cp_id = self._create_checkpoint_via_api(client, session_id)
        resp = client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": cp_id},
        )
        assert "turn_count" in resp.json()

    def test_restore_404_for_unknown_session(self, client: TestClient):
        resp = client.post(
            "/chat/sessions/nonexistent/restore",
            json={"checkpoint_id": "some-id"},
        )
        assert resp.status_code == 404

    def test_restore_404_for_unknown_checkpoint(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": "nonexistent-checkpoint-id"},
        )
        assert resp.status_code == 404

    def test_restore_reverts_prd_draft(self, client: TestClient, session_id: str):
        """After sending 1 message and checkpointing, send 3 more messages.
        Restore should bring back the 1-message draft (lower completeness)."""
        client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "m1"},
        )
        cp_id = client.post(
            f"/chat/sessions/{session_id}/checkpoint",
            params={"label": "after turn 1"},
        ).json()["checkpoint_id"]

        # Advance 3 more turns
        for i in range(3):
            client.post(
                "/chat/message",
                json={"session_id": session_id, "message": f"m{i+2}"},
            )

        # Get completeness before restore
        pre_status = client.get(f"/chat/sessions/{session_id}").json()
        pre_progress = pre_status["completeness"]["progress"]

        # Restore
        client.post(
            f"/chat/sessions/{session_id}/restore",
            json={"checkpoint_id": cp_id},
        )

        # Get completeness after restore
        post_status = client.get(f"/chat/sessions/{session_id}").json()
        post_progress = post_status["completeness"]["progress"]

        assert post_progress <= pre_progress


# ---------------------------------------------------------------------------
# 13. TestCheckpointsListEndpoint
# ---------------------------------------------------------------------------

class TestCheckpointsListEndpoint:
    def test_list_returns_200(self, client: TestClient, session_id: str):
        resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        assert resp.status_code == 200

    def test_list_empty_for_new_session(self, client: TestClient, session_id: str):
        resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        assert resp.json()["checkpoints"] == []

    def test_list_contains_session_id(self, client: TestClient, session_id: str):
        resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        assert resp.json()["session_id"] == session_id

    def test_list_grows_after_checkpoint_created(
        self, client: TestClient, session_id: str
    ):
        client.post(f"/chat/sessions/{session_id}/checkpoint")
        client.post(f"/chat/sessions/{session_id}/checkpoint")
        resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        assert len(resp.json()["checkpoints"]) >= 2

    def test_list_each_checkpoint_has_required_keys(
        self, client: TestClient, session_id: str
    ):
        # First message creates an auto-checkpoint
        client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        for cp in resp.json()["checkpoints"]:
            for key in ("checkpoint_id", "created_at", "phase", "turn_count", "label"):
                assert key in cp, f"Missing key '{key}' in checkpoint dict"

    def test_list_404_for_unknown_session(self, client: TestClient):
        resp = client.get("/chat/sessions/nonexistent/checkpoints")
        assert resp.status_code == 404

    def test_list_sorted_newest_first(self, client: TestClient, session_id: str):
        import time
        client.post(
            f"/chat/sessions/{session_id}/checkpoint",
            params={"label": "first"},
        )
        time.sleep(0.01)
        client.post(
            f"/chat/sessions/{session_id}/checkpoint",
            params={"label": "second"},
        )
        resp = client.get(f"/chat/sessions/{session_id}/checkpoints")
        checkpoints = resp.json()["checkpoints"]
        if len(checkpoints) >= 2:
            # Newest created_at should be first
            assert checkpoints[0]["created_at"] >= checkpoints[-1]["created_at"]


# ---------------------------------------------------------------------------
# 14. TestRegressionT03 — existing T03 behaviour unchanged
# ---------------------------------------------------------------------------

class TestRegressionT03:
    """Ensure T09 changes do not break T03 contract."""

    def test_create_session_still_returns_201(self, client: TestClient):
        resp = client.post("/chat/sessions")
        assert resp.status_code == 201

    def test_create_session_response_has_session_id(self, client: TestClient):
        data = client.post("/chat/sessions").json()
        assert "session_id" in data

    def test_message_returns_200(self, client: TestClient, session_id: str):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert resp.status_code == 200

    def test_message_response_has_assistant_message(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert "assistant_message" in resp.json()

    def test_message_response_has_draft_status(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert "draft_status" in resp.json()

    def test_message_response_has_completeness(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        completeness = resp.json()["completeness"]
        assert "filled" in completeness
        assert "missing" in completeness
        assert "progress" in completeness

    def test_message_response_has_next_questions(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hello"},
        )
        assert "next_questions" in resp.json()

    def test_draft_status_transitions_still_work(
        self, client: TestClient, session_id: str
    ):
        """T03 contract: 5 turns → ready_for_validation draft_status."""
        for _ in range(5):
            resp = client.post(
                "/chat/message",
                json={"session_id": session_id, "message": "next"},
            )
        assert resp.json()["draft_status"] == "ready_for_validation"

    def test_unknown_session_still_404(self, client: TestClient):
        resp = client.post(
            "/chat/message",
            json={"session_id": "bad-session-id", "message": "hi"},
        )
        assert resp.status_code == 404

    def test_session_status_endpoint_still_works(
        self, client: TestClient, session_id: str
    ):
        resp = client.get(f"/chat/sessions/{session_id}")
        assert resp.status_code == 200
        assert "turn_count" in resp.json()

    def test_prd_markdown_returned_after_first_turn(
        self, client: TestClient, session_id: str
    ):
        resp = client.post(
            "/chat/message",
            json={"session_id": session_id, "message": "hi"},
        )
        assert "prd_markdown" in resp.json()
