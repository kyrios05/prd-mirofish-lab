"""
tests/test_markdown_renderer.py — Unit + integration tests for T04 renderer.

Test groups
-----------
  1. TestEdgeCases            – None, {}, non-dict, minimal skeleton
  2. TestDeterminism          – same input → identical output (called twice)
  3. TestSectionHeadings      – all 14 section headings present in full PRD
  4. TestPartialPRD           – turn-2 partial: only rendered sections appear
  5. TestBilingualHeadings    – ko-KR vs en-US heading switching
  6. TestTableFormatting      – key_features, requirements, risks, metrics,
                                stakeholders, assumptions, open_questions
  7. TestSubElementRendering  – personas, user_journey, scope bullets, etc.
  8. TestChatAPIIntegration   – prd_markdown in ChatResponse via TestClient
  9. TestRendererContract     – return type, UTF-8, no trailing whitespace lines

Scope guard: no LLM calls, no DB, no MiroFish.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.markdown_renderer import (
    _gfm_table,
    _bullet_list,
    render_prd_markdown,
)
from app.services.mock_prd_builder import build_turn_delta
from app.services.session_store import session_store

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def _build_draft(turns: int, session_id: str = "test-session-abc") -> dict:
    """Build a partial PRD by applying `turns` mock turns."""
    draft: dict = {"schema_version": "0.1.0"}
    for i in range(1, turns + 1):
        delta, _ = build_turn_delta(i, session_id)
        draft.update(delta)
    return draft


@pytest.fixture(autouse=True)
def clear_session_store():
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
def minimal_prd() -> dict:
    return load_fixture("sample_prd_minimal.json")


@pytest.fixture
def full_prd() -> dict:
    return load_fixture("sample_prd_full.json")


@pytest.fixture
def turn1_draft() -> dict:
    return _build_draft(1)


@pytest.fixture
def turn2_draft() -> dict:
    return _build_draft(2)


@pytest.fixture
def full_mock_draft() -> dict:
    return _build_draft(5)


# ---------------------------------------------------------------------------
# 1. TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_none_input_returns_string(self):
        result = render_prd_markdown(None)
        assert isinstance(result, str)

    def test_none_input_no_error(self):
        # Must not raise
        render_prd_markdown(None)

    def test_empty_dict_returns_string(self):
        result = render_prd_markdown({})
        assert isinstance(result, str)

    def test_empty_dict_no_error(self):
        render_prd_markdown({})

    def test_empty_dict_returns_placeholder(self):
        result = render_prd_markdown({})
        assert len(result.strip()) > 0

    def test_schema_version_only_dict_no_error(self):
        render_prd_markdown({"schema_version": "0.1.0"})

    def test_schema_version_only_returns_nonempty(self):
        result = render_prd_markdown({"schema_version": "0.1.0"})
        assert isinstance(result, str) and len(result) > 0

    def test_minimal_fixture_no_error(self, minimal_prd: dict):
        render_prd_markdown(minimal_prd)

    def test_full_fixture_no_error(self, full_prd: dict):
        render_prd_markdown(full_prd)

    def test_partial_no_error(self, turn1_draft: dict):
        render_prd_markdown(turn1_draft)


# ---------------------------------------------------------------------------
# 2. TestDeterminism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_minimal_input_twice(self, minimal_prd: dict):
        r1 = render_prd_markdown(minimal_prd)
        r2 = render_prd_markdown(minimal_prd)
        assert r1 == r2

    def test_same_full_input_twice(self, full_prd: dict):
        r1 = render_prd_markdown(full_prd)
        r2 = render_prd_markdown(full_prd)
        assert r1 == r2

    def test_same_mock_full_draft_twice(self, full_mock_draft: dict):
        r1 = render_prd_markdown(full_mock_draft)
        r2 = render_prd_markdown(full_mock_draft)
        assert r1 == r2

    def test_different_inputs_different_outputs(self, turn1_draft: dict, turn2_draft: dict):
        r1 = render_prd_markdown(turn1_draft)
        r2 = render_prd_markdown(turn2_draft)
        assert r1 != r2

    def test_empty_input_deterministic(self):
        r1 = render_prd_markdown({})
        r2 = render_prd_markdown({})
        assert r1 == r2


# ---------------------------------------------------------------------------
# 3. TestSectionHeadings
# ---------------------------------------------------------------------------

class TestSectionHeadings:
    """All 14 section headings must appear in a fully-rendered PRD."""

    KO_HEADINGS = [
        "메타데이터",
        "제품 개요",
        "사용자",
        "문제 정의",
        "솔루션",
        "범위",
        "요구사항",
        "성공 지표",
        "딜리버리",
        "가정사항",
        "리스크",
        "미결 사항",
        "검증 계획",
    ]

    def test_all_ko_headings_in_full_fixture(self, full_prd: dict):
        md = render_prd_markdown(full_prd)
        for heading in self.KO_HEADINGS:
            assert heading in md, f"Heading '{heading}' not found"

    def test_all_ko_headings_in_mock_full_draft(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        for heading in self.KO_HEADINGS:
            assert heading in md, f"Heading '{heading}' not found"

    def test_h1_title_present(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert md.startswith("# ")

    def test_h2_headings_use_double_hash(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        # At least 5 h2 headings
        h2_lines = [l for l in md.splitlines() if l.startswith("## ")]
        assert len(h2_lines) >= 5

    def test_minimal_fixture_has_metadata_heading(self, minimal_prd: dict):
        md = render_prd_markdown(minimal_prd)
        assert "메타데이터" in md

    def test_schema_version_appears_in_title_block(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "schema_version" in md or "0.1.0" in md


# ---------------------------------------------------------------------------
# 4. TestPartialPRD
# ---------------------------------------------------------------------------

class TestPartialPRD:
    """Partial PRDs (early turns) should render only present sections."""

    def test_turn1_has_metadata_heading(self, turn1_draft: dict):
        md = render_prd_markdown(turn1_draft)
        assert "메타데이터" in md

    def test_turn1_has_product_heading(self, turn1_draft: dict):
        md = render_prd_markdown(turn1_draft)
        assert "제품 개요" in md

    def test_turn1_lacks_users_heading(self, turn1_draft: dict):
        md = render_prd_markdown(turn1_draft)
        assert "사용자" not in md

    def test_turn1_lacks_risks_heading(self, turn1_draft: dict):
        md = render_prd_markdown(turn1_draft)
        assert "리스크" not in md

    def test_turn2_has_users_heading(self, turn2_draft: dict):
        md = render_prd_markdown(turn2_draft)
        assert "사용자" in md

    def test_turn2_has_problem_heading(self, turn2_draft: dict):
        md = render_prd_markdown(turn2_draft)
        assert "문제 정의" in md

    def test_turn2_lacks_solution_heading(self, turn2_draft: dict):
        md = render_prd_markdown(turn2_draft)
        assert "솔루션" not in md

    def test_turn2_lacks_risks_heading(self, turn2_draft: dict):
        md = render_prd_markdown(turn2_draft)
        assert "리스크" not in md

    def test_turn5_has_all_sections(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        for heading in TestSectionHeadings.KO_HEADINGS:
            assert heading in md, f"Full draft missing: {heading}"


# ---------------------------------------------------------------------------
# 5. TestBilingualHeadings
# ---------------------------------------------------------------------------

class TestBilingualHeadings:
    def _make_prd_with_language(self, base: dict, language: str) -> dict:
        """Clone base dict and override metadata.language."""
        import copy
        prd = copy.deepcopy(base)
        if "metadata" not in prd or not prd["metadata"]:
            prd["metadata"] = {}
        prd["metadata"]["language"] = language
        return prd

    def test_ko_kr_uses_korean_metadata_heading(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "ko-KR")
        md = render_prd_markdown(prd)
        assert "메타데이터" in md
        assert "Metadata" not in md.split("메타데이터")[1][:5]

    def test_en_us_uses_english_metadata_heading(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "en-US")
        md = render_prd_markdown(prd)
        assert "Metadata" in md

    def test_en_us_uses_english_product_heading(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "en-US")
        md = render_prd_markdown(prd)
        assert "Product Overview" in md

    def test_en_us_uses_english_risks_heading(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "en-US")
        md = render_prd_markdown(prd)
        assert "Risks" in md

    def test_en_us_uses_english_solution_heading(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "en-US")
        md = render_prd_markdown(prd)
        assert "Solution" in md

    def test_en_us_uses_english_validation_heading(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "en-US")
        md = render_prd_markdown(prd)
        assert "Validation Plan" in md

    def test_unknown_language_defaults_to_korean(self, full_mock_draft: dict):
        prd = self._make_prd_with_language(full_mock_draft, "fr-FR")
        md = render_prd_markdown(prd)
        assert "메타데이터" in md

    def test_no_language_defaults_to_korean(self, full_mock_draft: dict):
        import copy
        prd = copy.deepcopy(full_mock_draft)
        if "metadata" in prd and prd["metadata"]:
            prd["metadata"].pop("language", None)
        md = render_prd_markdown(prd)
        assert "메타데이터" in md


# ---------------------------------------------------------------------------
# 6. TestTableFormatting
# ---------------------------------------------------------------------------

class TestTableFormatting:
    """GFM pipe tables must use | header | syntax with separator row."""

    def _has_pipe_table(self, md: str) -> bool:
        """Check that the markdown contains at least one GFM pipe table."""
        lines = md.splitlines()
        for line in lines:
            if re.match(r"^\|.+\|.+\|", line):
                return True
        return False

    def _has_separator_row(self, md: str) -> bool:
        return bool(re.search(r"^\| ?---", md, re.MULTILINE))

    def test_full_draft_has_pipe_table(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert self._has_pipe_table(md)

    def test_full_draft_has_table_separator_row(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert self._has_separator_row(md)

    def test_key_features_table_has_priority_column(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "우선순위" in md

    def test_requirements_table_has_id_column(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "FR-01" in md or "FR-" in md

    def test_risks_table_has_severity_column(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        # severity column header or a severity value
        assert "심각도" in md

    def test_assumptions_table_has_tag_column(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "태그" in md

    def test_stakeholders_table_present(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "검토 각도" in md

    def test_product_metrics_table_has_target_column(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "목표값" in md

    def test_gfm_table_helper_empty_rows(self):
        result = _gfm_table(["A", "B"], [])
        assert result == ""

    def test_gfm_table_helper_single_row(self):
        result = _gfm_table(["Name", "Value"], [["foo", "bar"]])
        assert "| Name | Value |" in result
        assert "| --- | --- |" in result
        assert "| foo | bar |" in result

    def test_gfm_table_helper_pipe_escaping(self):
        result = _gfm_table(["A"], [["val|ue"]])
        assert "val\\|ue" in result

    def test_bullet_list_helper_empty(self):
        assert _bullet_list([]) == ""
        assert _bullet_list(None) == ""

    def test_bullet_list_helper_items(self):
        result = _bullet_list(["a", "b"])
        assert "- a" in result
        assert "- b" in result


# ---------------------------------------------------------------------------
# 7. TestSubElementRendering
# ---------------------------------------------------------------------------

class TestSubElementRendering:
    def test_persona_name_in_output(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        # mock builder creates persona "PM 김지수"
        assert "PM 김지수" in md

    def test_persona_role_in_output(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "Product Manager" in md

    def test_user_journey_steps_rendered_as_ordered_list(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        # ordered list items
        assert re.search(r"^\d+\.", md, re.MULTILINE)

    def test_mvp_in_scope_uses_checkmark_header(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "✅" in md

    def test_out_of_scope_uses_x_header(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "❌" in md

    def test_scope_has_bullet_items(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "- " in md

    def test_delivery_priority_rendered(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "Priority" in md or "priority" in md.lower()

    def test_north_star_metric_rendered(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "North Star" in md

    def test_product_name_in_h1(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        first_line = md.splitlines()[0]
        assert first_line.startswith("# ")
        assert "[Mock]" in first_line  # mock builder name starts with [Mock]

    def test_schema_version_in_title_block(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "0.1.0" in md

    def test_industry_context_list_rendered(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        # industry_context is list[str] per T01 fix
        assert "B2B SaaS" in md

    def test_launch_constraints_list_rendered(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "Mock 모드" in md

    def test_open_questions_table_rendered(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "미결 사항" in md
        # At least one question text from mock builder
        assert "MiroFish" in md or "API" in md

    def test_risks_mitigation_in_table(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "완화책" in md

    def test_acceptance_criteria_rendered(self, full_mock_draft: dict):
        md = render_prd_markdown(full_mock_draft)
        assert "인수 기준" in md


# ---------------------------------------------------------------------------
# 8. TestChatAPIIntegration
# ---------------------------------------------------------------------------

class TestChatAPIIntegration:
    def _send(self, client: TestClient, sid: str, msg: str = "계속") -> dict:
        resp = client.post("/chat/message", json={"session_id": sid, "message": msg})
        assert resp.status_code == 200
        return resp.json()

    def test_prd_markdown_field_present_in_response(
        self, client: TestClient, session_id: str
    ):
        data = self._send(client, session_id)
        assert "prd_markdown" in data

    def test_prd_markdown_is_string_after_turn1(
        self, client: TestClient, session_id: str
    ):
        data = self._send(client, session_id)
        assert isinstance(data["prd_markdown"], str)
        assert len(data["prd_markdown"]) > 0

    def test_prd_markdown_none_before_any_turn(
        self, client: TestClient, session_id: str
    ):
        # session status endpoint doesn't expose prd_markdown,
        # but ChatResponse for the FIRST message should already have markdown
        # because mock builder produces draft on turn 1.
        # Verify: before first turn, structured_prd is None via session status
        status = client.get(f"/chat/sessions/{session_id}").json()
        assert status["has_prd_draft"] is False

    def test_prd_markdown_has_metadata_heading_after_turn1(
        self, client: TestClient, session_id: str
    ):
        data = self._send(client, session_id)
        assert "메타데이터" in data["prd_markdown"]

    def test_prd_markdown_has_product_heading_after_turn1(
        self, client: TestClient, session_id: str
    ):
        data = self._send(client, session_id)
        assert "제품 개요" in data["prd_markdown"]

    def test_prd_markdown_grows_with_turns(
        self, client: TestClient, session_id: str
    ):
        data1 = self._send(client, session_id)
        data2 = self._send(client, session_id)
        # More sections → longer markdown
        assert len(data2["prd_markdown"]) > len(data1["prd_markdown"])

    def test_prd_markdown_all_headings_after_turn5(
        self, client: TestClient, session_id: str
    ):
        for _ in range(5):
            data = self._send(client, session_id)
        md = data["prd_markdown"]
        for heading in [
            "메타데이터", "제품 개요", "사용자", "문제 정의",
            "솔루션", "범위", "요구사항", "성공 지표",
            "딜리버리", "가정사항", "리스크", "미결 사항", "검증 계획",
        ]:
            assert heading in md, f"Heading '{heading}' missing after turn 5"

    def test_prd_markdown_deterministic_same_session(
        self, client: TestClient, session_id: str
    ):
        # Same data (no new turn between calls) — markdown should be same
        # after one turn; re-check the same response content
        data1 = self._send(client, session_id)
        md1 = data1["prd_markdown"]
        # Render the same structured_prd again via the renderer directly
        from app.services.markdown_renderer import render_prd_markdown
        md2 = render_prd_markdown(data1["structured_prd"])
        assert md1 == md2


# ---------------------------------------------------------------------------
# 9. TestRendererContract
# ---------------------------------------------------------------------------

class TestRendererContract:
    def test_return_type_is_str(self, full_mock_draft: dict):
        result = render_prd_markdown(full_mock_draft)
        assert type(result) is str

    def test_output_ends_with_newline(self, full_mock_draft: dict):
        result = render_prd_markdown(full_mock_draft)
        assert result.endswith("\n")

    def test_output_is_valid_utf8(self, full_mock_draft: dict):
        result = render_prd_markdown(full_mock_draft)
        encoded = result.encode("utf-8")
        assert encoded.decode("utf-8") == result

    def test_output_has_no_double_blank_lines_of_3_or_more(
        self, full_mock_draft: dict
    ):
        result = render_prd_markdown(full_mock_draft)
        # Should not have 3+ consecutive blank lines
        assert "\n\n\n\n" not in result

    def test_full_fixture_output_length_nonzero(self, full_prd: dict):
        result = render_prd_markdown(full_prd)
        assert len(result) > 200

    def test_minimal_fixture_output_length_nonzero(self, minimal_prd: dict):
        result = render_prd_markdown(minimal_prd)
        assert len(result) > 100

    def test_none_input_output_contains_placeholder(self):
        result = render_prd_markdown(None)
        assert "미입력" in result or "Not Filled" in result or "PRD" in result

    def test_empty_dict_output_contains_placeholder(self):
        result = render_prd_markdown({})
        assert len(result.strip()) > 0
