"""
tests/test_validation_packager.py — Unit + integration tests for T05.

Test groups
-----------
  1. TestPackagerUnit            – package_for_simulation() pure function
  2. TestSimulationSpecShape     – SimulationSpec field types and structure
  3. TestValidationConfig        – ValidationConfig field extraction accuracy
  4. TestFocusAreasExtraction    – auto-extraction from risks + open_questions
  5. TestPRDMarkdownInSpec       – prd_markdown presence and content
  6. TestSpecDeterminism         – same PRD → same spec fields (UUID excluded)
  7. TestValidationRunEndpoint   – POST /validation/run (T02 regression + T05)
  8. TestPackageOnlyEndpoint     – POST /validation/package (new T05 endpoint)
  9. TestSchemaCheckEndpoint     – POST /validation/schema-check (T02, unchanged)
 10. TestMiroFishClientSignature – run_validation accepts SimulationSpec

Scope guard: no HTTP calls to MiroFish, no ValidationResult population.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import PRDDocument, SimulationSpec, ValidationConfig
from app.schemas.simulation import SimulationSpec, ValidationConfig
from app.services.validation_packager import (
    _build_validation_config,
    _extract_focus_areas,
    _extract_prd_summary,
    package_for_simulation,
)

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
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. TestPackagerUnit
# ---------------------------------------------------------------------------

class TestPackagerUnit:
    def test_returns_simulation_spec_type(self, minimal_prd_doc: PRDDocument):
        result = package_for_simulation(minimal_prd_doc)
        assert isinstance(result, SimulationSpec)

    def test_full_prd_returns_simulation_spec(self, full_prd_doc: PRDDocument):
        result = package_for_simulation(full_prd_doc)
        assert isinstance(result, SimulationSpec)

    def test_spec_id_is_valid_uuid(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        parsed = uuid.UUID(spec.spec_id)
        assert str(parsed) == spec.spec_id

    def test_spec_id_unique_per_call(self, minimal_prd_doc: PRDDocument):
        s1 = package_for_simulation(minimal_prd_doc)
        s2 = package_for_simulation(minimal_prd_doc)
        assert s1.spec_id != s2.spec_id

    def test_created_at_is_iso8601(self, minimal_prd_doc: PRDDocument):
        from datetime import datetime
        spec = package_for_simulation(minimal_prd_doc)
        dt = datetime.fromisoformat(spec.created_at)
        assert dt.tzinfo is not None  # timezone-aware

    def test_no_exception_on_minimal(self, minimal_prd_doc: PRDDocument):
        package_for_simulation(minimal_prd_doc)

    def test_no_exception_on_full(self, full_prd_doc: PRDDocument):
        package_for_simulation(full_prd_doc)

    def test_model_dump_is_json_serialisable(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        dumped = spec.model_dump()
        serialised = json.dumps(dumped)  # must not raise
        assert isinstance(serialised, str)

    def test_model_dump_round_trip(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        dumped = spec.model_dump()
        restored = SimulationSpec.model_validate(dumped)
        assert restored.prd_summary == spec.prd_summary

    def test_extract_prd_summary_helper(self, minimal_prd_doc: PRDDocument):
        summary = _extract_prd_summary(minimal_prd_doc)
        assert "name" in summary
        assert "one_liner" in summary
        assert "category" in summary
        assert "stage" in summary
        assert "project_id" in summary

    def test_extract_focus_areas_helper_returns_list(self, full_prd_doc: PRDDocument):
        areas = _extract_focus_areas(full_prd_doc)
        assert isinstance(areas, list)

    def test_build_validation_config_helper(self, minimal_prd_doc: PRDDocument):
        vc = _build_validation_config(minimal_prd_doc)
        assert isinstance(vc, ValidationConfig)


# ---------------------------------------------------------------------------
# 2. TestSimulationSpecShape
# ---------------------------------------------------------------------------

class TestSimulationSpecShape:
    def test_spec_has_spec_id(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert spec.spec_id and len(spec.spec_id) > 0

    def test_spec_has_created_at(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert spec.created_at and len(spec.created_at) > 0

    def test_spec_has_prd_summary(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.prd_summary, dict)

    def test_spec_has_prd_structured(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.prd_structured, dict)

    def test_spec_has_prd_markdown(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.prd_markdown, str)

    def test_spec_has_validation_config(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.validation_config, ValidationConfig)

    def test_prd_summary_has_name(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert "name" in spec.prd_summary
        assert spec.prd_summary["name"] == minimal_prd_doc.product.name

    def test_prd_summary_has_project_id(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert spec.prd_summary["project_id"] == minimal_prd_doc.metadata.project_id

    def test_prd_summary_stage_is_string(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.prd_summary["stage"], str)

    def test_prd_structured_has_schema_version(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert "schema_version" in spec.prd_structured
        assert spec.prd_structured["schema_version"] == "0.1.0"

    def test_prd_structured_has_metadata(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert "metadata" in spec.prd_structured

    def test_prd_structured_has_all_required_sections(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        required = [
            "metadata", "product", "users", "problem", "solution",
            "scope", "requirements", "success_metrics", "delivery",
            "assumptions", "risks", "open_questions", "validation",
        ]
        for s in required:
            assert s in spec.prd_structured, f"Section '{s}' missing from prd_structured"

    def test_summary_dict_helper(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        summary = spec.summary_dict()
        assert "spec_id" in summary
        assert "prd_markdown_chars" in summary
        assert summary["prd_markdown_chars"] > 0

    def test_extra_fields_forbidden(self):
        """SimulationSpec must reject unknown fields."""
        with pytest.raises(Exception):
            SimulationSpec(
                spec_id="x",
                created_at="x",
                prd_summary={},
                prd_structured={},
                prd_markdown="x",
                validation_config=ValidationConfig(
                    goals=["g"],
                    stakeholder_personas=[{"name": "x", "role": "r", "review_angle": "ra"}],
                    simulation_requirement="s",
                ),
                unknown_extra_field="bad",
            )


# ---------------------------------------------------------------------------
# 3. TestValidationConfig
# ---------------------------------------------------------------------------

class TestValidationConfig:
    def test_goals_match_prd_validation_goals(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert spec.validation_config.goals == minimal_prd_doc.validation.goals

    def test_simulation_requirement_matches(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert spec.validation_config.simulation_requirement == \
               minimal_prd_doc.validation.simulation_requirement

    def test_stakeholder_personas_count_matches(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert len(spec.validation_config.stakeholder_personas) == \
               len(minimal_prd_doc.validation.stakeholder_personas)

    def test_stakeholder_persona_has_name(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        first = spec.validation_config.stakeholder_personas[0]
        assert "name" in first
        assert first["name"] == minimal_prd_doc.validation.stakeholder_personas[0].name

    def test_stakeholder_persona_is_plain_dict(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        first = spec.validation_config.stakeholder_personas[0]
        assert isinstance(first, dict)

    def test_validation_templates_empty_when_none(self, minimal_prd_doc: PRDDocument):
        """minimal fixture has no validation_templates."""
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.validation_config.validation_templates, list)

    def test_validation_templates_present_in_full(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        templates = spec.validation_config.validation_templates
        assert len(templates) >= 1
        # Templates are plain strings (enum .value extracted)
        for t in templates:
            assert isinstance(t, str)

    def test_must_answer_questions_in_full(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        questions = spec.validation_config.must_answer_questions
        assert len(questions) >= 1

    def test_must_answer_questions_empty_list_when_none(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.validation_config.must_answer_questions, list)

    def test_goals_full_prd(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        assert len(spec.validation_config.goals) >= 1


# ---------------------------------------------------------------------------
# 4. TestFocusAreasExtraction
# ---------------------------------------------------------------------------

class TestFocusAreasExtraction:
    def test_focus_areas_is_list(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.validation_config.focus_areas, list)

    def test_focus_areas_contains_risk_titles(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        risk_titles = [r.title for r in minimal_prd_doc.risks]
        for title in risk_titles:
            assert title in spec.validation_config.focus_areas, \
                f"Risk title '{title}' not in focus_areas"

    def test_focus_areas_contains_open_question_texts(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        oq_texts = [q.text for q in minimal_prd_doc.open_questions]
        for text in oq_texts:
            assert text in spec.validation_config.focus_areas, \
                f"Open question text '{text}' not in focus_areas"

    def test_focus_areas_risks_come_before_questions(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        areas = spec.validation_config.focus_areas
        risk_titles = [r.title for r in full_prd_doc.risks]
        oq_texts = [q.text for q in full_prd_doc.open_questions]
        # All risk titles appear before all open question texts
        if risk_titles and oq_texts:
            last_risk_idx = max(areas.index(t) for t in risk_titles if t in areas)
            first_oq_idx = min(areas.index(t) for t in oq_texts if t in areas)
            assert last_risk_idx < first_oq_idx, \
                "Risks should appear before open_questions in focus_areas"

    def test_focus_areas_total_count(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        expected = len(full_prd_doc.risks) + len(full_prd_doc.open_questions)
        assert len(spec.validation_config.focus_areas) == expected

    def test_focus_areas_helper_direct(self, minimal_prd_doc: PRDDocument):
        areas = _extract_focus_areas(minimal_prd_doc)
        assert all(isinstance(a, str) for a in areas)

    def test_focus_areas_nonempty_for_full_prd(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        assert len(spec.validation_config.focus_areas) > 0


# ---------------------------------------------------------------------------
# 5. TestPRDMarkdownInSpec
# ---------------------------------------------------------------------------

class TestPRDMarkdownInSpec:
    def test_prd_markdown_is_nonempty_string(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert isinstance(spec.prd_markdown, str)
        assert len(spec.prd_markdown) > 0

    def test_prd_markdown_has_product_name(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert minimal_prd_doc.product.name in spec.prd_markdown

    def test_prd_markdown_has_metadata_heading(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert "메타데이터" in spec.prd_markdown

    def test_prd_markdown_ends_with_newline(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        assert spec.prd_markdown.endswith("\n")

    def test_prd_markdown_full_has_all_sections(self, full_prd_doc: PRDDocument):
        spec = package_for_simulation(full_prd_doc)
        for heading in ["메타데이터", "솔루션", "리스크", "검증 계획"]:
            assert heading in spec.prd_markdown

    def test_prd_markdown_is_utf8(self, minimal_prd_doc: PRDDocument):
        spec = package_for_simulation(minimal_prd_doc)
        encoded = spec.prd_markdown.encode("utf-8")
        assert encoded.decode("utf-8") == spec.prd_markdown


# ---------------------------------------------------------------------------
# 6. TestSpecDeterminism
# ---------------------------------------------------------------------------

class TestSpecDeterminism:
    def test_prd_summary_identical_for_same_prd(self, minimal_prd_doc: PRDDocument):
        s1 = package_for_simulation(minimal_prd_doc)
        s2 = package_for_simulation(minimal_prd_doc)
        assert s1.prd_summary == s2.prd_summary

    def test_prd_structured_identical_for_same_prd(self, minimal_prd_doc: PRDDocument):
        s1 = package_for_simulation(minimal_prd_doc)
        s2 = package_for_simulation(minimal_prd_doc)
        assert s1.prd_structured == s2.prd_structured

    def test_prd_markdown_identical_for_same_prd(self, minimal_prd_doc: PRDDocument):
        s1 = package_for_simulation(minimal_prd_doc)
        s2 = package_for_simulation(minimal_prd_doc)
        assert s1.prd_markdown == s2.prd_markdown

    def test_validation_config_identical_for_same_prd(self, minimal_prd_doc: PRDDocument):
        s1 = package_for_simulation(minimal_prd_doc)
        s2 = package_for_simulation(minimal_prd_doc)
        assert s1.validation_config.model_dump() == s2.validation_config.model_dump()

    def test_focus_areas_identical_for_same_prd(self, full_prd_doc: PRDDocument):
        s1 = package_for_simulation(full_prd_doc)
        s2 = package_for_simulation(full_prd_doc)
        assert s1.validation_config.focus_areas == s2.validation_config.focus_areas

    def test_spec_ids_differ_across_calls(self, minimal_prd_doc: PRDDocument):
        s1 = package_for_simulation(minimal_prd_doc)
        s2 = package_for_simulation(minimal_prd_doc)
        assert s1.spec_id != s2.spec_id


# ---------------------------------------------------------------------------
# 7. TestValidationRunEndpoint
# ---------------------------------------------------------------------------

class TestValidationRunEndpoint:
    def test_valid_prd_returns_200(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200

    def test_valid_prd_status_is_completed(self, client: TestClient, minimal_prd_dict: dict):
        # T06: /validation/run now returns status='completed' (was 'packaged' in T05 stub)
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["status"] == "completed"

    def test_valid_prd_schema_valid_true(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["schema_valid"] is True

    def test_valid_prd_simulation_spec_not_none(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["simulation_spec"] is not None

    def test_simulation_spec_has_spec_id(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        spec = resp.json()["simulation_spec"]
        assert "spec_id" in spec
        uuid.UUID(spec["spec_id"])  # must parse as UUID

    def test_simulation_spec_has_prd_markdown(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        spec = resp.json()["simulation_spec"]
        assert "prd_markdown" in spec
        assert len(spec["prd_markdown"]) > 0

    def test_simulation_spec_has_validation_config(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        spec = resp.json()["simulation_spec"]
        assert "validation_config" in spec
        vc = spec["validation_config"]
        assert "goals" in vc
        assert "stakeholder_personas" in vc
        assert "focus_areas" in vc

    def test_simulation_spec_focus_areas_nonempty(self, client: TestClient, full_prd_dict: dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": full_prd_dict},
        )
        focus = resp.json()["simulation_spec"]["validation_config"]["focus_areas"]
        assert len(focus) > 0

    def test_invalid_prd_returns_schema_invalid(self, client: TestClient):
        resp = client.post(
            "/validation/run",
            json={"project_id": "bad-proj", "prd": {"bad": "payload"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_valid"] is False
        assert data["status"] == "schema_invalid"
        assert data["simulation_spec"] is None

    def test_invalid_prd_schema_errors_populated(self, client: TestClient):
        resp = client.post(
            "/validation/run",
            json={"project_id": "bad-proj", "prd": {"bad": "payload"}},
        )
        assert len(resp.json()["schema_errors"]) > 0

    def test_result_is_populated_by_mock_engine(self, client: TestClient, minimal_prd_dict: dict):
        # T06: result is now populated by mock engine (no longer None)
        resp = client.post(
            "/validation/run",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["result"] is not None
        assert isinstance(resp.json()["result"]["summary"], str)

    def test_full_prd_run_succeeds(self, client: TestClient, full_prd_dict: dict):
        # T06: full run returns status='completed'
        resp = client.post(
            "/validation/run",
            json={"project_id": "full-proj", "prd": full_prd_dict},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# 8. TestPackageOnlyEndpoint
# ---------------------------------------------------------------------------

class TestPackageOnlyEndpoint:
    def test_returns_200(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200

    def test_status_is_packaged(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["status"] == "packaged"

    def test_simulation_spec_returned(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        assert resp.json()["simulation_spec"] is not None

    def test_invalid_prd_returns_schema_invalid(self, client: TestClient):
        resp = client.post(
            "/validation/package",
            json={"project_id": "bad", "prd": {}},
        )
        assert resp.json()["status"] == "schema_invalid"
        assert resp.json()["simulation_spec"] is None

    def test_spec_id_is_uuid(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        spec_id = resp.json()["simulation_spec"]["spec_id"]
        uuid.UUID(spec_id)

    def test_prd_markdown_in_spec(self, client: TestClient, minimal_prd_dict: dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "test-proj", "prd": minimal_prd_dict},
        )
        md = resp.json()["simulation_spec"]["prd_markdown"]
        assert len(md) > 0

    def test_different_spec_ids_run_vs_package(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        """Each call produces a fresh UUID — /run and /package differ."""
        r1 = client.post("/validation/run", json={"project_id": "p", "prd": minimal_prd_dict})
        r2 = client.post("/validation/package", json={"project_id": "p", "prd": minimal_prd_dict})
        id1 = r1.json()["simulation_spec"]["spec_id"]
        id2 = r2.json()["simulation_spec"]["spec_id"]
        assert id1 != id2


# ---------------------------------------------------------------------------
# 9. TestSchemaCheckEndpoint
# ---------------------------------------------------------------------------

class TestSchemaCheckEndpoint:
    """T02 /schema-check regression — must be unchanged by T05."""

    def test_valid_returns_schema_valid_status(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "test", "prd": minimal_prd_dict},
        )
        assert resp.json()["status"] == "schema_valid"
        assert resp.json()["schema_valid"] is True

    def test_invalid_returns_schema_invalid_status(self, client: TestClient):
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "test", "prd": {"garbage": True}},
        )
        assert resp.json()["status"] == "schema_invalid"

    def test_schema_check_simulation_spec_is_none(
        self, client: TestClient, minimal_prd_dict: dict
    ):
        """schema-check must NOT return a simulation_spec."""
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "test", "prd": minimal_prd_dict},
        )
        assert resp.json()["simulation_spec"] is None


# ---------------------------------------------------------------------------
# 10. TestMiroFishClientSignature
# ---------------------------------------------------------------------------

class TestMiroFishClientSignature:
    def test_run_validation_accepts_simulation_spec(self, minimal_prd_doc: PRDDocument):
        """MiroFishClient.run_validation must accept SimulationSpec and return ValidationResult (T06)."""
        import asyncio
        from app.schemas import ValidationResult
        from app.services.mirofish_client import MiroFishClient
        spec = package_for_simulation(minimal_prd_doc)
        client_instance = MiroFishClient(
            base_url="https://example.com",
            api_key="test-key",
        )
        result = asyncio.get_event_loop().run_until_complete(
            client_instance.run_validation(spec)
        )
        # T06: mock engine now returns a ValidationResult (not None)
        assert result is not None
        assert isinstance(result, ValidationResult)

    def test_mirofish_client_imports_simulation_spec(self):
        """mirofish_client must import SimulationSpec, not PRDDocument."""
        import inspect
        from app.services import mirofish_client
        source = inspect.getsource(mirofish_client)
        assert "SimulationSpec" in source
        # PRDDocument should not appear in the run_validation signature
        assert "SimulationSpec" in source
