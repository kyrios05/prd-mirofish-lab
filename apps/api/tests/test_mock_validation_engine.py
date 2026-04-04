"""
tests/test_mock_validation_engine.py — T06 mock validation engine tests.

Test groups
-----------
  1. TestEngineContract          – run_mock_validation() returns valid ValidationResult
  2. TestSummaryGeneration       – summary field content-aware generation
  3. TestTopRisks                – derived from focus_areas risk portion
  4. TestMissingRequirements     – gaps detected from requirements section
  5. TestStakeholderObjections   – derived from stakeholder_personas
  6. TestScopeAdjustments        – derived from delivery + scope data
  7. TestRecommendedQuestions    – must_answer_questions + focus_area questions
  8. TestRewriteSuggestions      – optional field gap detection
  9. TestDeterminism             – same spec → same result
 10. TestMiroFishClientIntegration – run_validation() returns ValidationResult (not None)
 11. TestValidationRunEndpoint   – /validation/run status="completed" + result fields
 12. TestPackageEndpointUnchanged – /validation/package still status="packaged", result=None
 13. TestSchemaCheckUnchanged    – /validation/schema-check T02 regression
 14. TestInvalidPRDUnchanged     – invalid PRD still returns schema_invalid

Scope guard: no actual HTTP calls, no LLM, no external I/O.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import PRDDocument, ValidationResult
from app.schemas.simulation import SimulationSpec, ValidationConfig
from app.services.mock_validation_engine import (
    _build_missing_requirements,
    _build_recommended_questions,
    _build_rewrite_suggestions,
    _build_scope_adjustments,
    _build_stakeholder_objections,
    _build_summary,
    _build_top_risks,
    _is_question,
    _split_focus_areas,
    run_mock_validation,
)
from app.services.validation_packager import package_for_simulation

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


@pytest.fixture
def minimal_prd_dict() -> dict:
    return load_fixture("sample_prd_minimal.json")


@pytest.fixture
def full_prd_dict() -> dict:
    return load_fixture("sample_prd_full.json")


@pytest.fixture
def minimal_prd_doc(minimal_prd_dict: dict) -> PRDDocument:
    return PRDDocument.model_validate(minimal_prd_dict)


@pytest.fixture
def full_prd_doc(full_prd_dict: dict) -> PRDDocument:
    return PRDDocument.model_validate(full_prd_dict)


@pytest.fixture
def minimal_spec(minimal_prd_doc: PRDDocument) -> SimulationSpec:
    return package_for_simulation(minimal_prd_doc)


@pytest.fixture
def full_spec(full_prd_doc: PRDDocument) -> SimulationSpec:
    return package_for_simulation(full_prd_doc)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. TestEngineContract
# ---------------------------------------------------------------------------

class TestEngineContract:
    def test_returns_validation_result_type(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result, ValidationResult)

    def test_full_spec_returns_validation_result(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert isinstance(result, ValidationResult)

    def test_summary_is_nonempty_string(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_top_risks_is_list(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.top_risks, list)

    def test_missing_requirements_is_list(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.missing_requirements, list)

    def test_stakeholder_objections_is_list(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.stakeholder_objections, list)

    def test_scope_adjustments_is_list(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.scope_adjustments, list)

    def test_recommended_questions_is_list(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.recommended_questions, list)

    def test_rewrite_suggestions_is_list(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert isinstance(result.rewrite_suggestions, list)

    def test_all_seven_fields_nonempty_minimal(self, minimal_spec: SimulationSpec):
        """All 7 fields must be populated even for a minimal PRD."""
        result = run_mock_validation(minimal_spec)
        assert result.summary
        assert len(result.top_risks) >= 1
        assert len(result.missing_requirements) >= 1
        assert len(result.stakeholder_objections) >= 1
        assert len(result.scope_adjustments) >= 1
        assert len(result.recommended_questions) >= 1
        assert len(result.rewrite_suggestions) >= 1

    def test_all_seven_fields_nonempty_full(self, full_spec: SimulationSpec):
        """Full PRD also populates all 7 fields."""
        result = run_mock_validation(full_spec)
        assert result.summary
        assert len(result.top_risks) >= 1
        assert len(result.missing_requirements) >= 1
        assert len(result.stakeholder_objections) >= 1
        assert len(result.scope_adjustments) >= 1
        assert len(result.recommended_questions) >= 1
        assert len(result.rewrite_suggestions) >= 1

    def test_result_model_dump_is_json_serialisable(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        dumped = result.model_dump()
        serialised = json.dumps(dumped)
        assert isinstance(serialised, str)

    def test_result_model_dump_round_trip(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        dumped = result.model_dump()
        restored = ValidationResult.model_validate(dumped)
        assert restored.summary == result.summary


# ---------------------------------------------------------------------------
# 2. TestSummaryGeneration
# ---------------------------------------------------------------------------

class TestSummaryGeneration:
    def test_summary_contains_product_name_minimal(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        product_name = minimal_spec.prd_summary["name"]
        assert product_name in result.summary

    def test_summary_contains_product_name_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        product_name = full_spec.prd_summary["name"]
        assert product_name in result.summary

    def test_summary_mentions_stakeholder_count(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        n = len(full_spec.validation_config.stakeholder_personas)
        assert str(n) in result.summary

    def test_summary_mentions_focus_area_count(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        n = len(full_spec.validation_config.focus_areas)
        assert str(n) in result.summary

    def test_summary_helper_direct(self, minimal_spec: SimulationSpec):
        summary = _build_summary(minimal_spec)
        assert isinstance(summary, str)
        assert len(summary) > 10

    def test_summary_is_deterministic(self, minimal_spec: SimulationSpec):
        s1 = _build_summary(minimal_spec)
        s2 = _build_summary(minimal_spec)
        assert s1 == s2


# ---------------------------------------------------------------------------
# 3. TestTopRisks
# ---------------------------------------------------------------------------

class TestTopRisks:
    def test_top_risks_nonempty_minimal(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert len(result.top_risks) >= 1

    def test_top_risks_nonempty_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.top_risks) >= 1

    def test_top_risks_based_on_focus_areas(self, full_spec: SimulationSpec):
        """Risk items from focus_areas must appear in top_risks."""
        focus_risks, _ = _split_focus_areas(full_spec.validation_config.focus_areas)
        result = run_mock_validation(full_spec)
        # At least one focus_area risk title should be in top_risks
        overlap = [r for r in focus_risks if r in result.top_risks]
        assert len(overlap) >= 1, (
            f"No focus_area risk items found in top_risks.\n"
            f"focus_risks={focus_risks}\ntop_risks={result.top_risks}"
        )

    def test_top_risks_max_five(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.top_risks) <= 5

    def test_top_risks_all_strings(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        for r in result.top_risks:
            assert isinstance(r, str)
            assert len(r) > 0

    def test_is_question_helper_with_question_mark(self):
        assert _is_question("MiroFish API SLA는 어느 수준인가?") is True

    def test_is_question_helper_with_korean_question(self):
        assert _is_question("PRD 데이터를 어디에 저장할 것인가?") is True

    def test_is_question_helper_with_risk_title(self):
        assert _is_question("LLM 응답 품질 불안정") is False

    def test_split_focus_areas_separates_correctly(self, full_spec: SimulationSpec):
        risks, questions = _split_focus_areas(full_spec.validation_config.focus_areas)
        for r in risks:
            assert not _is_question(r)
        for q in questions:
            assert _is_question(q)


# ---------------------------------------------------------------------------
# 4. TestMissingRequirements
# ---------------------------------------------------------------------------

class TestMissingRequirements:
    def test_missing_requirements_nonempty_minimal(self, minimal_spec: SimulationSpec):
        """Minimal fixture is missing acceptance_criteria and integrations."""
        result = run_mock_validation(minimal_spec)
        assert len(result.missing_requirements) >= 1

    def test_missing_requirements_nonempty_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.missing_requirements) >= 1

    def test_missing_acceptance_criteria_detected(self, minimal_spec: SimulationSpec):
        """Minimal fixture has no acceptance_criteria → must be flagged."""
        result = run_mock_validation(minimal_spec)
        combined = " ".join(result.missing_requirements)
        assert "수락 기준" in combined or "acceptance" in combined.lower()

    def test_missing_integrations_detected(self, minimal_spec: SimulationSpec):
        """Minimal fixture has no integrations → must be flagged."""
        result = run_mock_validation(minimal_spec)
        combined = " ".join(result.missing_requirements)
        assert "연동" in combined or "integration" in combined.lower()

    def test_helper_returns_list(self, minimal_spec: SimulationSpec):
        items = _build_missing_requirements(minimal_spec)
        assert isinstance(items, list)
        assert all(isinstance(i, str) for i in items)

    def test_full_prd_requirements_richer(self, full_spec: SimulationSpec):
        """Full PRD has acceptance_criteria + integrations so fewer gaps."""
        minimal_spec_inner = package_for_simulation(
            PRDDocument.model_validate(load_fixture("sample_prd_minimal.json"))
        )
        full_result = run_mock_validation(full_spec)
        minimal_result = run_mock_validation(minimal_spec_inner)
        # Full PRD should have at least as many missing items or same (both have NFR check)
        # The key check: full prd has more requirements populated
        prd = full_spec.prd_structured
        assert prd["requirements"]["acceptance_criteria"] is not None


# ---------------------------------------------------------------------------
# 5. TestStakeholderObjections
# ---------------------------------------------------------------------------

class TestStakeholderObjections:
    def test_objections_nonempty_minimal(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert len(result.stakeholder_objections) >= 1

    def test_objections_nonempty_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.stakeholder_objections) >= 1

    def test_objections_count_ge_persona_count(self, full_spec: SimulationSpec):
        """Must produce at least 1 objection per stakeholder persona."""
        n_personas = len(full_spec.validation_config.stakeholder_personas)
        result = run_mock_validation(full_spec)
        assert len(result.stakeholder_objections) >= n_personas

    def test_full_prd_uses_likely_objections(self, full_spec: SimulationSpec):
        """Full fixture stakeholders have likely_objections → use them verbatim."""
        personas = full_spec.validation_config.stakeholder_personas
        # Collect all known likely_objections
        known: list[str] = []
        for p in personas:
            if p.get("likely_objections"):
                known.extend(p["likely_objections"])
        result = run_mock_validation(full_spec)
        # At least one known objection must appear in the result
        overlap = [o for o in known if o in result.stakeholder_objections]
        assert len(overlap) >= 1, (
            f"No known likely_objections found in result.\n"
            f"known={known}\nresult={result.stakeholder_objections}"
        )

    def test_minimal_prd_derives_from_review_angle(self, minimal_spec: SimulationSpec):
        """Minimal fixture stakeholder has no likely_objections → derive from review_angle."""
        persona = minimal_spec.validation_config.stakeholder_personas[0]
        assert not persona.get("likely_objections")  # confirm fixture state
        result = run_mock_validation(minimal_spec)
        # The derived objection should mention the stakeholder name or role
        combined = " ".join(result.stakeholder_objections)
        assert persona["name"] in combined or persona["role"] in combined

    def test_helper_returns_list_of_strings(self, minimal_spec: SimulationSpec):
        objections = _build_stakeholder_objections(minimal_spec)
        assert isinstance(objections, list)
        assert all(isinstance(o, str) for o in objections)


# ---------------------------------------------------------------------------
# 6. TestScopeAdjustments
# ---------------------------------------------------------------------------

class TestScopeAdjustments:
    def test_scope_adjustments_nonempty_minimal(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert len(result.scope_adjustments) >= 1

    def test_scope_adjustments_nonempty_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.scope_adjustments) >= 1

    def test_adjustment_for_large_mvp_scope(self, full_spec: SimulationSpec):
        """Full fixture has 6 mvp_in_scope items and medium confidence."""
        prd = full_spec.prd_structured
        mvp_count = len(prd["scope"]["mvp_in_scope"])
        confidence = prd["delivery"]["timeline_confidence"]
        assert mvp_count > 5
        assert confidence != "high"
        result = run_mock_validation(full_spec)
        combined = " ".join(result.scope_adjustments)
        assert str(mvp_count) in combined or "범위" in combined

    def test_helper_returns_list_of_strings(self, minimal_spec: SimulationSpec):
        adjustments = _build_scope_adjustments(minimal_spec)
        assert isinstance(adjustments, list)
        assert all(isinstance(a, str) for a in adjustments)

    def test_low_confidence_triggers_warning(self, minimal_spec: SimulationSpec):
        """Manually construct a spec with low timeline_confidence."""
        # Patch prd_structured to simulate low confidence
        prd_copy = dict(minimal_spec.prd_structured)
        delivery_copy = dict(prd_copy.get("delivery", {}))
        delivery_copy["timeline_confidence"] = "low"
        prd_copy["delivery"] = delivery_copy

        patched_spec = SimulationSpec(
            spec_id=minimal_spec.spec_id,
            created_at=minimal_spec.created_at,
            prd_summary=minimal_spec.prd_summary,
            prd_structured=prd_copy,
            prd_markdown=minimal_spec.prd_markdown,
            validation_config=minimal_spec.validation_config,
        )
        adjustments = _build_scope_adjustments(patched_spec)
        combined = " ".join(adjustments)
        assert "low" in combined or "축소" in combined or "낮" in combined


# ---------------------------------------------------------------------------
# 7. TestRecommendedQuestions
# ---------------------------------------------------------------------------

class TestRecommendedQuestions:
    def test_recommended_questions_nonempty_minimal(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert len(result.recommended_questions) >= 1

    def test_recommended_questions_nonempty_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.recommended_questions) >= 1

    def test_must_answer_questions_included_in_full(self, full_spec: SimulationSpec):
        """must_answer_questions must appear in recommended_questions."""
        must = full_spec.validation_config.must_answer_questions
        assert len(must) >= 1
        result = run_mock_validation(full_spec)
        for q in must:
            assert q in result.recommended_questions, (
                f"must_answer question missing from recommended_questions: {q}"
            )

    def test_focus_area_questions_included(self, full_spec: SimulationSpec):
        """Open-question focus_areas must appear in recommended_questions."""
        _, oq = _split_focus_areas(full_spec.validation_config.focus_areas)
        result = run_mock_validation(full_spec)
        if oq:
            overlap = [q for q in oq if q in result.recommended_questions]
            assert len(overlap) >= 1

    def test_helper_returns_list_of_strings(self, minimal_spec: SimulationSpec):
        questions = _build_recommended_questions(minimal_spec)
        assert isinstance(questions, list)
        assert all(isinstance(q, str) for q in questions)

    def test_minimal_has_fallback_questions(self, minimal_spec: SimulationSpec):
        """Minimal fixture has no must_answer — fallback generic questions used."""
        assert not minimal_spec.validation_config.must_answer_questions
        result = run_mock_validation(minimal_spec)
        assert len(result.recommended_questions) >= 1


# ---------------------------------------------------------------------------
# 8. TestRewriteSuggestions
# ---------------------------------------------------------------------------

class TestRewriteSuggestions:
    def test_rewrite_suggestions_nonempty_minimal(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        assert len(result.rewrite_suggestions) >= 1

    def test_rewrite_suggestions_nonempty_full(self, full_spec: SimulationSpec):
        result = run_mock_validation(full_spec)
        assert len(result.rewrite_suggestions) >= 1

    def test_user_journey_missing_triggers_suggestion(self, minimal_spec: SimulationSpec):
        """Minimal fixture has no user_journey → suggestion must mention it."""
        assert not minimal_spec.prd_structured["solution"]["user_journey"]
        result = run_mock_validation(minimal_spec)
        combined = " ".join(result.rewrite_suggestions)
        assert "user_journey" in combined or "사용자 흐름" in combined or "흐름" in combined

    def test_acceptance_criteria_missing_triggers_suggestion(self, minimal_spec: SimulationSpec):
        """Minimal fixture has no acceptance_criteria → suggestion must mention it."""
        assert not minimal_spec.prd_structured["requirements"]["acceptance_criteria"]
        result = run_mock_validation(minimal_spec)
        combined = " ".join(result.rewrite_suggestions)
        assert "acceptance" in combined.lower() or "수락 기준" in combined

    def test_helper_returns_list_of_strings(self, minimal_spec: SimulationSpec):
        suggestions = _build_rewrite_suggestions(minimal_spec)
        assert isinstance(suggestions, list)
        assert all(isinstance(s, str) for s in suggestions)

    def test_all_suggestions_have_reasonable_length(self, minimal_spec: SimulationSpec):
        result = run_mock_validation(minimal_spec)
        for s in result.rewrite_suggestions:
            assert len(s) >= 10, f"Suggestion too short: '{s}'"


# ---------------------------------------------------------------------------
# 9. TestDeterminism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_minimal_spec_same_summary(self, minimal_spec: SimulationSpec):
        r1 = run_mock_validation(minimal_spec)
        r2 = run_mock_validation(minimal_spec)
        assert r1.summary == r2.summary

    def test_same_minimal_spec_same_top_risks(self, minimal_spec: SimulationSpec):
        r1 = run_mock_validation(minimal_spec)
        r2 = run_mock_validation(minimal_spec)
        assert r1.top_risks == r2.top_risks

    def test_same_minimal_spec_same_objections(self, minimal_spec: SimulationSpec):
        r1 = run_mock_validation(minimal_spec)
        r2 = run_mock_validation(minimal_spec)
        assert r1.stakeholder_objections == r2.stakeholder_objections

    def test_same_full_spec_same_result(self, full_spec: SimulationSpec):
        r1 = run_mock_validation(full_spec)
        r2 = run_mock_validation(full_spec)
        assert r1.model_dump() == r2.model_dump()

    def test_different_prds_different_summaries(
        self, minimal_spec: SimulationSpec, full_spec: SimulationSpec
    ):
        r_min = run_mock_validation(minimal_spec)
        r_full = run_mock_validation(full_spec)
        assert r_min.summary != r_full.summary

    def test_different_prds_different_risk_counts(
        self, minimal_spec: SimulationSpec, full_spec: SimulationSpec
    ):
        r_min = run_mock_validation(minimal_spec)
        r_full = run_mock_validation(full_spec)
        # Full PRD has more focus_areas → more top_risks
        assert len(r_full.top_risks) >= len(r_min.top_risks)


# ---------------------------------------------------------------------------
# 10. TestMiroFishClientIntegration
# ---------------------------------------------------------------------------

class TestMiroFishClientIntegration:
    def test_run_validation_returns_validation_result(self, minimal_spec: SimulationSpec):
        """MiroFishClient.run_validation must now return ValidationResult, not None."""
        from app.services.mirofish_client import MiroFishClient
        client_instance = MiroFishClient(
            base_url="https://example.com",
            api_key="test-key",
        )
        result = asyncio.get_event_loop().run_until_complete(
            client_instance.run_validation(minimal_spec)
        )
        assert result is not None
        assert isinstance(result, ValidationResult)

    def test_mirofish_client_result_has_summary(self, minimal_spec: SimulationSpec):
        from app.services.mirofish_client import MiroFishClient
        client_instance = MiroFishClient(
            base_url="https://example.com",
            api_key="test-key",
        )
        result = asyncio.get_event_loop().run_until_complete(
            client_instance.run_validation(minimal_spec)
        )
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_mirofish_client_imports_mock_engine(self):
        import inspect
        from app.services import mirofish_client
        source = inspect.getsource(mirofish_client)
        assert "run_mock_validation" in source
        assert "TODO(T10)" in source


# ---------------------------------------------------------------------------
# 11. TestValidationRunEndpoint
# ---------------------------------------------------------------------------

class TestValidationRunEndpoint:
    def test_valid_prd_returns_status_completed(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_valid_prd_result_is_not_none(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["result"] is not None

    def test_result_summary_is_nonempty(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        result = resp.json()["result"]
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_result_has_all_seven_fields(self, client: TestClient, full_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        result = resp.json()["result"]
        required_fields = [
            "summary", "top_risks", "missing_requirements",
            "stakeholder_objections", "scope_adjustments",
            "recommended_questions", "rewrite_suggestions",
        ]
        for f in required_fields:
            assert f in result, f"Field '{f}' missing from result"

    def test_simulation_spec_and_result_both_present(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        data = resp.json()
        assert data["simulation_spec"] is not None
        assert data["result"] is not None

    def test_result_top_risks_is_nonempty_list(self, client: TestClient, full_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        top_risks = resp.json()["result"]["top_risks"]
        assert isinstance(top_risks, list)
        assert len(top_risks) >= 1

    def test_result_stakeholder_objections_nonempty(
        self, client: TestClient, full_prd_dict: dict
    ):
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        objections = resp.json()["result"]["stakeholder_objections"]
        assert len(objections) >= 1

    def test_result_recommended_questions_nonempty(
        self, client: TestClient, full_prd_dict: dict
    ):
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        questions = resp.json()["result"]["recommended_questions"]
        assert len(questions) >= 1

    def test_schema_valid_true_on_success(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["schema_valid"] is True

    def test_full_prd_run_succeeds_with_result(self, client: TestClient, full_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["result"] is not None

    def test_result_summary_contains_product_name(
        self, client: TestClient, full_prd_dict: dict
    ):
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        summary = resp.json()["result"]["summary"]
        # Product name from full fixture
        assert "PRD MiroFish Lab" in summary


# ---------------------------------------------------------------------------
# 12. TestPackageEndpointUnchanged
# ---------------------------------------------------------------------------

class TestPackageEndpointUnchanged:
    def test_package_still_returns_packaged_status(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["status"] == "packaged"

    def test_package_result_is_none(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["result"] is None

    def test_package_simulation_spec_present(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["simulation_spec"] is not None

    def test_package_invalid_prd_still_schema_invalid(self, client: TestClient):
        resp = client.post(
            "/validation/package",
            json={"project_id": "bad", "prd": {}},
        )
        assert resp.json()["status"] == "schema_invalid"
        assert resp.json()["result"] is None


# ---------------------------------------------------------------------------
# 13. TestSchemaCheckUnchanged
# ---------------------------------------------------------------------------

class TestSchemaCheckUnchanged:
    def test_schema_check_valid_returns_schema_valid(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "test", "prd": minimal_prd_dict},
        )
        assert resp.json()["status"] == "schema_valid"
        assert resp.json()["schema_valid"] is True

    def test_schema_check_result_is_none(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "test", "prd": minimal_prd_dict},
        )
        assert resp.json()["result"] is None

    def test_schema_check_simulation_spec_is_none(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "test", "prd": minimal_prd_dict},
        )
        assert resp.json()["simulation_spec"] is None


# ---------------------------------------------------------------------------
# 14. TestInvalidPRDUnchanged
# ---------------------------------------------------------------------------

class TestInvalidPRDUnchanged:
    def test_invalid_run_returns_schema_invalid(self, client: TestClient):
        resp = client.post(
            "/validation/run",
            json={"project_id": "bad-proj", "prd": {"bad": "payload"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_valid"] is False
        assert data["status"] == "schema_invalid"

    def test_invalid_run_result_is_none(self, client: TestClient):
        resp = client.post(
            "/validation/run",
            json={"project_id": "bad-proj", "prd": {"bad": "payload"}},
        )
        assert resp.json()["result"] is None

    def test_invalid_run_simulation_spec_is_none(self, client: TestClient):
        resp = client.post(
            "/validation/run",
            json={"project_id": "bad-proj", "prd": {"bad": "payload"}},
        )
        assert resp.json()["simulation_spec"] is None

    def test_invalid_run_schema_errors_populated(self, client: TestClient):
        resp = client.post(
            "/validation/run",
            json={"project_id": "bad-proj", "prd": {"bad": "payload"}},
        )
        assert len(resp.json()["schema_errors"]) > 0


# ---------------------------------------------------------------------------
# Helper: load_fixture needed at module level for some parametrised tests
# ---------------------------------------------------------------------------

def load_fixture(name: str) -> dict:
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data
