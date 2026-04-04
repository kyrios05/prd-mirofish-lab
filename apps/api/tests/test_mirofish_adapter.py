"""
tests/test_mirofish_adapter.py — T10 MiroFish adapter and client tests.

Test groups
-----------
  1.  TestMiroFishJobModel          – MiroFishJob dataclass: fields, transitions, to_dict
  2.  TestMiroFishJobStatus         – MiroFishJobStatus enum values
  3.  TestResponseMapper            – _map_mirofish_response: mapping, fallbacks, edge cases
  4.  TestAdapterInit               – MiroFishAdapter initialisation
  5.  TestAdapterSubmitValidation   – submit_validation(): HTTP call sequence (respx)
  6.  TestAdapterPollPrepareStatus  – _poll_prepare_status() state machine
  7.  TestAdapterPollUntilComplete  – poll_until_complete() polling logic
  8.  TestAdapterGetResult          – get_result() fetch + mapping
  9.  TestAdapterRetryBehavior      – Exponential backoff on HTTP errors
 10.  TestAdapterFullLifecycle      – run_full_lifecycle() happy path + failures
 11.  TestMiroFishClientInit        – MiroFishClient __init__ + mode setting
 12.  TestMiroFishClientMockMode    – mode="mock" → run_mock_validation called
 13.  TestMiroFishClientLiveMode    – mode="live" → adapter called (respx)
 14.  TestMiroFishClientFallback    – live failure + fallback_to_mock=True/False
 15.  TestMiroFishClientFactory     – make_mirofish_client() uses settings
 16.  TestValidationRouteMode       – /validation/run: validation_mode field
 17.  TestValidationRouteRegression – existing /validation/run behaviour unchanged
 18.  TestConfigT10Settings         – Settings has all T10 fields with correct defaults
 19.  TestBuildCreatePayload        – _build_create_payload() mapping

Scope guard
-----------
  - mock_validation_engine: used as comparison baseline, NOT modified
  - SimulationSpec / ValidationResult schemas: not changed
  - No actual MiroFish server required (all HTTP calls mocked via respx)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.config import Settings
from app.schemas import ValidationResult
from app.schemas.simulation import SimulationSpec, ValidationConfig
from app.services.mock_validation_engine import run_mock_validation
from app.services.mirofish_adapter import (
    MiroFishAdapter,
    MiroFishJob,
    MiroFishJobStatus,
    _build_create_payload,
    _map_mirofish_response,
)
from app.services.mirofish_client import (
    MiroFishClient,
    _make_sentinel_job,
    make_mirofish_client,
)
from app.services.validation_packager import package_for_simulation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(filename: str) -> dict:
    data = json.loads((FIXTURES_DIR / filename).read_text())
    data.pop("_comment", None)
    return data


@pytest.fixture
def minimal_prd_dict() -> dict:
    return _load("sample_prd_minimal.json")


@pytest.fixture
def full_prd_dict() -> dict:
    return _load("sample_prd_full.json")


@pytest.fixture
def sim_spec(minimal_prd_dict) -> SimulationSpec:
    from app.schemas import PRDDocument
    doc = PRDDocument.model_validate(minimal_prd_dict)
    return package_for_simulation(doc)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# Fake MiroFish HTTP responses used across multiple test classes
MIROFISH_CREATE_RESP = {"simulation_id": "sim-abc123", "status": "created"}
MIROFISH_PREPARE_RESP = {"task_id": "task-xyz789", "status": "preparing"}
MIROFISH_PREPARE_STATUS_READY = {"status": "ready", "progress": 1.0}
MIROFISH_RUN_RESP = {"status": "running"}
MIROFISH_SIM_COMPLETED = {"status": "completed", "progress": 1.0}
MIROFISH_REPORT = {
    "summary": "MiroFish validated the product successfully.",
    "top_risks": ["Risk A", "Risk B"],
    "missing_requirements": ["NFR-001 missing"],
    "stakeholder_objections": ["CFO objects to timeline"],
    "scope_adjustments": ["Reduce MVP scope"],
    "recommended_questions": ["What is the integration plan?"],
    "rewrite_suggestions": ["Expand acceptance criteria"],
}


# ---------------------------------------------------------------------------
# 1. TestMiroFishJobModel
# ---------------------------------------------------------------------------

class TestMiroFishJobModel:
    def test_default_fields(self):
        job = MiroFishJob()
        assert job.job_id is not None
        assert len(job.job_id) == 36  # UUID format
        assert job.simulation_id is None
        assert job.task_id is None
        assert job.status == MiroFishJobStatus.CREATED
        assert job.progress == 0.0
        assert job.error is None
        assert job.result is None
        assert job.created_at is not None
        assert job.updated_at is not None

    def test_update_status(self):
        job = MiroFishJob()
        job._update(status=MiroFishJobStatus.RUNNING, progress=0.5)
        assert job.status == MiroFishJobStatus.RUNNING
        assert job.progress == 0.5

    def test_update_error(self):
        job = MiroFishJob()
        job._update(status=MiroFishJobStatus.FAILED, error="network error")
        assert job.status == MiroFishJobStatus.FAILED
        assert job.error == "network error"

    def test_to_dict_keys(self):
        job = MiroFishJob()
        d = job.to_dict()
        expected_keys = {
            "job_id", "simulation_id", "task_id", "status",
            "progress", "created_at", "updated_at", "error",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_status_is_string(self):
        job = MiroFishJob()
        job._update(status=MiroFishJobStatus.COMPLETED)
        assert job.to_dict()["status"] == "completed"

    def test_to_dict_does_not_include_result(self):
        """result is internal; callers get it separately."""
        job = MiroFishJob()
        assert "result" not in job.to_dict()

    def test_unique_job_ids(self):
        ids = {MiroFishJob().job_id for _ in range(20)}
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# 2. TestMiroFishJobStatus
# ---------------------------------------------------------------------------

class TestMiroFishJobStatus:
    def test_all_values_exist(self):
        values = {s.value for s in MiroFishJobStatus}
        assert values == {"created", "preparing", "ready", "running", "completed", "failed"}

    def test_is_str_enum(self):
        assert isinstance(MiroFishJobStatus.COMPLETED, str)
        assert MiroFishJobStatus.COMPLETED == "completed"

    def test_json_serialisable(self):
        job = MiroFishJob()
        d = job.to_dict()
        json.dumps(d)  # should not raise


# ---------------------------------------------------------------------------
# 3. TestResponseMapper
# ---------------------------------------------------------------------------

class TestResponseMapper:
    def test_full_mapping(self, sim_spec):
        result = _map_mirofish_response(MIROFISH_REPORT, sim_spec)
        assert isinstance(result, ValidationResult)
        assert result.summary == MIROFISH_REPORT["summary"]
        assert result.top_risks == MIROFISH_REPORT["top_risks"]
        assert result.missing_requirements == MIROFISH_REPORT["missing_requirements"]
        assert result.stakeholder_objections == MIROFISH_REPORT["stakeholder_objections"]
        assert result.scope_adjustments == MIROFISH_REPORT["scope_adjustments"]
        assert result.recommended_questions == MIROFISH_REPORT["recommended_questions"]
        assert result.rewrite_suggestions == MIROFISH_REPORT["rewrite_suggestions"]

    def test_fallback_keys_top_risks(self, sim_spec):
        """'risks' → top_risks fallback."""
        raw = {"summary": "s", "risks": ["R1", "R2"]}
        result = _map_mirofish_response(raw, sim_spec)
        assert result is not None
        assert result.top_risks == ["R1", "R2"]

    def test_fallback_keys_questions(self, sim_spec):
        raw = {"summary": "s", "questions": ["Q1"]}
        result = _map_mirofish_response(raw, sim_spec)
        assert result is not None
        assert result.recommended_questions == ["Q1"]

    def test_fallback_keys_suggestions(self, sim_spec):
        raw = {"summary": "s", "suggestions": ["Fix intro"]}
        result = _map_mirofish_response(raw, sim_spec)
        assert result is not None
        assert result.rewrite_suggestions == ["Fix intro"]

    def test_missing_summary_uses_product_name(self, sim_spec):
        raw: dict[str, Any] = {}
        result = _map_mirofish_response(raw, sim_spec)
        assert result is not None
        assert len(result.summary) > 0

    def test_empty_arrays_on_missing_fields(self, sim_spec):
        raw = {"summary": "ok"}
        result = _map_mirofish_response(raw, sim_spec)
        assert result is not None
        assert result.top_risks == []
        assert result.missing_requirements == []

    def test_non_dict_returns_none(self, sim_spec):
        result = _map_mirofish_response("not a dict", sim_spec)  # type: ignore
        assert result is None

    def test_none_returns_none(self, sim_spec):
        result = _map_mirofish_response(None, sim_spec)  # type: ignore
        assert result is None

    def test_list_input_returns_none(self, sim_spec):
        result = _map_mirofish_response(["a", "b"], sim_spec)  # type: ignore
        assert result is None

    def test_overview_key_for_summary(self, sim_spec):
        raw = {"overview": "Product overview here"}
        result = _map_mirofish_response(raw, sim_spec)
        assert result is not None
        assert result.summary == "Product overview here"

    def test_result_is_validation_result_type(self, sim_spec):
        result = _map_mirofish_response(MIROFISH_REPORT, sim_spec)
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# 4. TestAdapterInit
# ---------------------------------------------------------------------------

class TestAdapterInit:
    def test_default_values(self):
        a = MiroFishAdapter()
        assert a.base_url == "http://localhost:5001"
        assert a.api_key == ""
        assert a.timeout == 30
        assert a.max_retries == 3
        assert a.polling_interval == 2.0
        assert a.max_polling_attempts == 150

    def test_custom_values(self):
        a = MiroFishAdapter(
            base_url="http://mirofish:9000",
            api_key="secret",
            timeout=60,
            max_retries=5,
            polling_interval=0.5,
            max_polling_attempts=10,
        )
        assert a.base_url == "http://mirofish:9000"
        assert a.api_key == "secret"
        assert a.timeout == 60
        assert a.max_retries == 5
        assert a.polling_interval == 0.5
        assert a.max_polling_attempts == 10

    def test_trailing_slash_stripped(self):
        a = MiroFishAdapter(base_url="http://localhost:5001/")
        assert a.base_url == "http://localhost:5001"

    def test_headers_include_api_key(self):
        a = MiroFishAdapter(api_key="mykey")
        h = a._headers()
        assert h["Authorization"] == "Bearer mykey"
        assert h["X-API-Key"] == "mykey"

    def test_headers_no_auth_when_empty_key(self):
        a = MiroFishAdapter(api_key="")
        h = a._headers()
        assert "Authorization" not in h


# ---------------------------------------------------------------------------
# 5. TestAdapterSubmitValidation
# ---------------------------------------------------------------------------

class TestAdapterSubmitValidation:
    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_path_call_sequence(self, sim_spec):
        """submit_validation() makes 4 HTTP calls in correct order."""
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(200, json=MIROFISH_CREATE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_STATUS_READY)
        )
        respx.post("http://mf:5001/api/simulation/sim-abc123/run").mock(
            return_value=httpx.Response(200, json=MIROFISH_RUN_RESP)
        )

        job = await adapter.submit_validation(sim_spec)

        assert job.simulation_id == "sim-abc123"
        assert job.task_id == "task-xyz789"
        assert job.status == MiroFishJobStatus.RUNNING
        assert job.error is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_failure_sets_failed(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=1,
            polling_interval=0.0,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(500, json={"error": "server error"})
        )
        job = await adapter.submit_validation(sim_spec)
        assert job.status == MiroFishJobStatus.FAILED
        assert job.error is not None
        assert "create failed" in job.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_prepare_failure_sets_failed(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=1,
            polling_interval=0.0,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(200, json=MIROFISH_CREATE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(500, json={"error": "prepare error"})
        )
        job = await adapter.submit_validation(sim_spec)
        assert job.status == MiroFishJobStatus.FAILED
        assert "prepare failed" in job.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_simulation_id_stored(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=2,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(200, json={"simulation_id": "SIM-999"})
        )
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_STATUS_READY)
        )
        respx.post("http://mf:5001/api/simulation/SIM-999/run").mock(
            return_value=httpx.Response(200, json=MIROFISH_RUN_RESP)
        )
        job = await adapter.submit_validation(sim_spec)
        assert job.simulation_id == "SIM-999"


# ---------------------------------------------------------------------------
# 6. TestAdapterPollPrepareStatus
# ---------------------------------------------------------------------------

class TestAdapterPollPrepareStatus:
    @pytest.mark.asyncio
    @respx.mock
    async def test_immediate_ready(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json={"status": "ready"})
        )
        job = MiroFishJob()
        job.simulation_id = "sim-1"
        job.task_id = "task-1"
        async with httpx.AsyncClient() as c:
            result = await adapter._poll_prepare_status(c, job)
        assert result.status == MiroFishJobStatus.READY

    @pytest.mark.asyncio
    @respx.mock
    async def test_transitions_through_preparing(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=10,
        )
        # First two calls return "preparing", then "ready"
        call_count = 0

        def side_effect(_request):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(200, json={"status": "preparing", "progress": 0.5})
            return httpx.Response(200, json={"status": "ready", "progress": 1.0})

        respx.post("http://mf:5001/api/simulation/prepare/status").mock(side_effect=side_effect)
        job = MiroFishJob()
        job.simulation_id = "sim-1"
        job.task_id = "task-1"
        async with httpx.AsyncClient() as c:
            result = await adapter._poll_prepare_status(c, job)
        assert result.status == MiroFishJobStatus.READY
        assert call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_sets_failed(self):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=2,
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json={"status": "preparing"})
        )
        job = MiroFishJob()
        job.simulation_id = "sim-1"
        async with httpx.AsyncClient() as c:
            result = await adapter._poll_prepare_status(c, job)
        assert result.status == MiroFishJobStatus.FAILED
        assert "timed out" in (result.error or "")

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_status_sets_failed(self):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json={"status": "failed", "error": "prepare error"})
        )
        job = MiroFishJob()
        job.simulation_id = "sim-1"
        async with httpx.AsyncClient() as c:
            result = await adapter._poll_prepare_status(c, job)
        assert result.status == MiroFishJobStatus.FAILED


# ---------------------------------------------------------------------------
# 7. TestAdapterPollUntilComplete
# ---------------------------------------------------------------------------

class TestAdapterPollUntilComplete:
    @pytest.mark.asyncio
    @respx.mock
    async def test_immediate_complete(self):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        job._update(status=MiroFishJobStatus.RUNNING)
        respx.get("http://mf:5001/api/simulation/sim-abc").mock(
            return_value=httpx.Response(200, json=MIROFISH_SIM_COMPLETED)
        )
        result = await adapter.poll_until_complete(job)
        assert result.status == MiroFishJobStatus.COMPLETED
        assert result.progress == 1.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_polls_until_completed(self):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=10,
        )
        call_count = 0

        def side_effect(_req):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(200, json={"status": "running", "progress": 0.5})
            return httpx.Response(200, json={"status": "completed", "progress": 1.0})

        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        job._update(status=MiroFishJobStatus.RUNNING)
        respx.get("http://mf:5001/api/simulation/sim-abc").mock(side_effect=side_effect)
        result = await adapter.poll_until_complete(job)
        assert result.status == MiroFishJobStatus.COMPLETED
        assert call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_simulation_failure_detected(self):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        respx.get("http://mf:5001/api/simulation/sim-abc").mock(
            return_value=httpx.Response(200, json={"status": "failed", "error": "oom"})
        )
        result = await adapter.poll_until_complete(job)
        assert result.status == MiroFishJobStatus.FAILED

    @pytest.mark.asyncio
    async def test_no_simulation_id_sets_failed(self):
        adapter = MiroFishAdapter(polling_interval=0.0)
        job = MiroFishJob()
        job.simulation_id = None
        result = await adapter.poll_until_complete(job)
        assert result.status == MiroFishJobStatus.FAILED

    @pytest.mark.asyncio
    @respx.mock
    async def test_polling_timeout(self):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=2,
        )
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        respx.get("http://mf:5001/api/simulation/sim-abc").mock(
            return_value=httpx.Response(200, json={"status": "running"})
        )
        result = await adapter.poll_until_complete(job)
        assert result.status == MiroFishJobStatus.FAILED
        assert "timed out" in (result.error or "")


# ---------------------------------------------------------------------------
# 8. TestAdapterGetResult
# ---------------------------------------------------------------------------

class TestAdapterGetResult:
    @pytest.mark.asyncio
    @respx.mock
    async def test_successful_result_mapping(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
        )
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        job._update(status=MiroFishJobStatus.COMPLETED, progress=1.0)

        respx.get("http://mf:5001/api/simulation/sim-abc/report").mock(
            return_value=httpx.Response(200, json=MIROFISH_REPORT)
        )
        result = await adapter.get_result(job, sim_spec)
        assert isinstance(result, ValidationResult)
        assert result.summary == MIROFISH_REPORT["summary"]

    @pytest.mark.asyncio
    async def test_non_completed_job_returns_none(self, sim_spec):
        adapter = MiroFishAdapter()
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        job._update(status=MiroFishJobStatus.RUNNING)
        result = await adapter.get_result(job, sim_spec)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_report_fetch_failure_returns_none(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=1,
            polling_interval=0.0,
        )
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        job._update(status=MiroFishJobStatus.COMPLETED)
        respx.get("http://mf:5001/api/simulation/sim-abc/report").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        result = await adapter.get_result(job, sim_spec)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_result_stored_on_job(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
        )
        job = MiroFishJob()
        job.simulation_id = "sim-abc"
        job._update(status=MiroFishJobStatus.COMPLETED)
        respx.get("http://mf:5001/api/simulation/sim-abc/report").mock(
            return_value=httpx.Response(200, json=MIROFISH_REPORT)
        )
        await adapter.get_result(job, sim_spec)
        assert job.result is not None
        assert isinstance(job.result, ValidationResult)


# ---------------------------------------------------------------------------
# 9. TestAdapterRetryBehavior
# ---------------------------------------------------------------------------

class TestAdapterRetryBehavior:
    @pytest.mark.asyncio
    @respx.mock
    async def test_post_retries_on_500(self, sim_spec):
        """Adapter retries on 500 and eventually succeeds."""
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=3,
            polling_interval=0.0,
        )
        call_count = 0

        def side_effect(_req):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500, json={"error": "transient"})
            return httpx.Response(200, json=MIROFISH_CREATE_RESP)

        respx.post("http://mf:5001/api/simulation/create").mock(side_effect=side_effect)
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_STATUS_READY)
        )
        respx.post("http://mf:5001/api/simulation/sim-abc123/run").mock(
            return_value=httpx.Response(200, json=MIROFISH_RUN_RESP)
        )
        job = await adapter.submit_validation(sim_spec)
        # Should eventually succeed after retries
        assert job.status == MiroFishJobStatus.RUNNING
        assert call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_raises_after_max_retries(self, sim_spec):
        """After max_retries all fail, job status = FAILED."""
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=2,
            polling_interval=0.0,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(500, json={"error": "permanent"})
        )
        job = await adapter.submit_validation(sim_spec)
        assert job.status == MiroFishJobStatus.FAILED


# ---------------------------------------------------------------------------
# 10. TestAdapterFullLifecycle
# ---------------------------------------------------------------------------

class TestAdapterFullLifecycle:
    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_path(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(200, json=MIROFISH_CREATE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_STATUS_READY)
        )
        respx.post("http://mf:5001/api/simulation/sim-abc123/run").mock(
            return_value=httpx.Response(200, json=MIROFISH_RUN_RESP)
        )
        respx.get("http://mf:5001/api/simulation/sim-abc123").mock(
            return_value=httpx.Response(200, json=MIROFISH_SIM_COMPLETED)
        )
        respx.get("http://mf:5001/api/simulation/sim-abc123/report").mock(
            return_value=httpx.Response(200, json=MIROFISH_REPORT)
        )
        result = await adapter.run_full_lifecycle(sim_spec)
        assert isinstance(result, ValidationResult)
        assert result.summary == MIROFISH_REPORT["summary"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_failure_returns_none(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=1,
            polling_interval=0.0,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(500, json={"error": "fail"})
        )
        result = await adapter.run_full_lifecycle(sim_spec)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_poll_timeout_returns_none(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            polling_interval=0.0,
            max_polling_attempts=2,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(200, json=MIROFISH_CREATE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_STATUS_READY)
        )
        respx.post("http://mf:5001/api/simulation/sim-abc123/run").mock(
            return_value=httpx.Response(200, json=MIROFISH_RUN_RESP)
        )
        # Poll always returns "running" → triggers timeout
        respx.get("http://mf:5001/api/simulation/sim-abc123").mock(
            return_value=httpx.Response(200, json={"status": "running"})
        )
        result = await adapter.run_full_lifecycle(sim_spec)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_report_mapping_failure_returns_none(self, sim_spec):
        adapter = MiroFishAdapter(
            base_url="http://mf:5001",
            max_retries=1,
            polling_interval=0.0,
            max_polling_attempts=5,
        )
        respx.post("http://mf:5001/api/simulation/create").mock(
            return_value=httpx.Response(200, json=MIROFISH_CREATE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_RESP)
        )
        respx.post("http://mf:5001/api/simulation/prepare/status").mock(
            return_value=httpx.Response(200, json=MIROFISH_PREPARE_STATUS_READY)
        )
        respx.post("http://mf:5001/api/simulation/sim-abc123/run").mock(
            return_value=httpx.Response(200, json=MIROFISH_RUN_RESP)
        )
        respx.get("http://mf:5001/api/simulation/sim-abc123").mock(
            return_value=httpx.Response(200, json=MIROFISH_SIM_COMPLETED)
        )
        # Report endpoint returns garbage
        respx.get("http://mf:5001/api/simulation/sim-abc123/report").mock(
            return_value=httpx.Response(500, json={"error": "report unavailable"})
        )
        result = await adapter.run_full_lifecycle(sim_spec)
        assert result is None


# ---------------------------------------------------------------------------
# 11. TestMiroFishClientInit
# ---------------------------------------------------------------------------

class TestMiroFishClientInit:
    def test_mock_mode_default(self):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k")
        assert c.mode == "mock"
        assert c._adapter is None

    def test_live_mode_creates_adapter(self):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="live")
        assert c.mode == "live"
        assert isinstance(c._adapter, MiroFishAdapter)

    def test_live_mode_case_insensitive(self):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="LIVE")
        assert c.mode == "live"

    def test_adapter_gets_correct_settings(self):
        c = MiroFishClient(
            base_url="http://mf:9999",
            api_key="secret",
            mode="live",
            timeout=45,
            max_retries=5,
            polling_interval=1.5,
            max_polling=50,
        )
        assert c._adapter.base_url == "http://mf:9999"
        assert c._adapter.api_key == "secret"
        assert c._adapter.timeout == 45
        assert c._adapter.max_retries == 5
        assert c._adapter.polling_interval == 1.5
        assert c._adapter.max_polling_attempts == 50

    def test_fallback_to_mock_default_true(self):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="live")
        assert c.fallback_to_mock is True

    def test_fallback_to_mock_configurable(self):
        c = MiroFishClient(
            base_url="http://mf:5001", api_key="k",
            mode="live", fallback_to_mock=False,
        )
        assert c.fallback_to_mock is False


# ---------------------------------------------------------------------------
# 12. TestMiroFishClientMockMode
# ---------------------------------------------------------------------------

class TestMiroFishClientMockMode:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_validation_result(self, sim_spec):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="mock")
        result = await c.run_validation(sim_spec)
        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_mock_mode_no_job_stored(self, sim_spec):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="mock")
        await c.run_validation(sim_spec)
        assert c.last_job is None

    @pytest.mark.asyncio
    async def test_mock_mode_deterministic(self, sim_spec):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="mock")
        r1 = await c.run_validation(sim_spec)
        r2 = await c.run_validation(sim_spec)
        assert r1.summary == r2.summary
        assert r1.top_risks == r2.top_risks

    @pytest.mark.asyncio
    async def test_mock_mode_matches_direct_engine_call(self, sim_spec):
        """MiroFishClient(mode=mock) result == run_mock_validation(spec)."""
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="mock")
        client_result = await c.run_validation(sim_spec)
        direct_result = run_mock_validation(sim_spec)
        assert client_result.summary == direct_result.summary
        assert client_result.top_risks == direct_result.top_risks

    @pytest.mark.asyncio
    async def test_mock_mode_does_not_call_adapter(self, sim_spec):
        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="mock")
        # _adapter should be None in mock mode
        assert c._adapter is None
        # Should not raise even though no adapter
        result = await c.run_validation(sim_spec)
        assert result is not None


# ---------------------------------------------------------------------------
# 13. TestMiroFishClientLiveMode
# ---------------------------------------------------------------------------

class TestMiroFishClientLiveMode:
    @pytest.mark.asyncio
    async def test_live_mode_calls_adapter(self, sim_spec):
        """mode=live delegates to adapter.run_full_lifecycle."""
        mock_result = ValidationResult(
            summary="live result",
            top_risks=[],
            missing_requirements=[],
            stakeholder_objections=[],
            scope_adjustments=[],
            recommended_questions=[],
            rewrite_suggestions=[],
        )
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(return_value=mock_result)

        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="live")
        c._adapter = mock_adapter

        result = await c.run_validation(sim_spec)
        mock_adapter.run_full_lifecycle.assert_called_once_with(sim_spec)
        assert result.summary == "live result"

    @pytest.mark.asyncio
    async def test_live_mode_stores_job(self, sim_spec):
        """After live-mode success, last_job is populated."""
        mock_result = ValidationResult(
            summary="ok",
            top_risks=[],
            missing_requirements=[],
            stakeholder_objections=[],
            scope_adjustments=[],
            recommended_questions=[],
            rewrite_suggestions=[],
        )
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(return_value=mock_result)

        c = MiroFishClient(base_url="http://mf:5001", api_key="k", mode="live")
        c._adapter = mock_adapter

        await c.run_validation(sim_spec)
        assert c.last_job is not None
        assert isinstance(c.last_job, MiroFishJob)
        assert c.last_job.status == MiroFishJobStatus.COMPLETED


# ---------------------------------------------------------------------------
# 14. TestMiroFishClientFallback
# ---------------------------------------------------------------------------

class TestMiroFishClientFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_adapter_none_result(self, sim_spec):
        """Adapter returns None → fallback_to_mock=True → mock result returned."""
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(return_value=None)

        c = MiroFishClient(
            base_url="http://mf:5001", api_key="k",
            mode="live", fallback_to_mock=True,
        )
        c._adapter = mock_adapter

        result = await c.run_validation(sim_spec)
        assert isinstance(result, ValidationResult)  # got mock fallback
        # Verify it matches direct mock output
        direct = run_mock_validation(sim_spec)
        assert result.summary == direct.summary

    @pytest.mark.asyncio
    async def test_no_fallback_returns_none_on_adapter_failure(self, sim_spec):
        """fallback_to_mock=False + adapter returns None → client returns None."""
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(return_value=None)

        c = MiroFishClient(
            base_url="http://mf:5001", api_key="k",
            mode="live", fallback_to_mock=False,
        )
        c._adapter = mock_adapter

        result = await c.run_validation(sim_spec)
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_on_adapter_exception(self, sim_spec):
        """Adapter raises → fallback_to_mock=True → mock result."""
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(
            side_effect=Exception("connection refused")
        )

        c = MiroFishClient(
            base_url="http://mf:5001", api_key="k",
            mode="live", fallback_to_mock=True,
        )
        c._adapter = mock_adapter

        result = await c.run_validation(sim_spec)
        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_no_fallback_on_exception_returns_none(self, sim_spec):
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(
            side_effect=RuntimeError("timeout")
        )

        c = MiroFishClient(
            base_url="http://mf:5001", api_key="k",
            mode="live", fallback_to_mock=False,
        )
        c._adapter = mock_adapter

        result = await c.run_validation(sim_spec)
        assert result is None

    @pytest.mark.asyncio
    async def test_job_stored_on_fallback(self, sim_spec):
        """Even when falling back, last_job is populated with FAILED status."""
        mock_adapter = AsyncMock(spec=MiroFishAdapter)
        mock_adapter.run_full_lifecycle = AsyncMock(return_value=None)

        c = MiroFishClient(
            base_url="http://mf:5001", api_key="k",
            mode="live", fallback_to_mock=True,
        )
        c._adapter = mock_adapter

        await c.run_validation(sim_spec)
        assert c.last_job is not None
        assert c.last_job.status == MiroFishJobStatus.FAILED


# ---------------------------------------------------------------------------
# 15. TestMiroFishClientFactory
# ---------------------------------------------------------------------------

class TestMiroFishClientFactory:
    def test_factory_returns_client(self):
        c = make_mirofish_client()
        assert isinstance(c, MiroFishClient)

    def test_factory_uses_settings_mode(self):
        # settings is a local import inside make_mirofish_client; patch it there
        with patch("app.config.settings") as mock_settings:
            mock_settings.mirofish_base_url = "http://mf:5001"
            mock_settings.mirofish_api_key = "key"
            mock_settings.mirofish_mode = "mock"
            mock_settings.mirofish_fallback_to_mock = True
            mock_settings.mirofish_polling_interval = 2.0
            mock_settings.mirofish_max_polling = 150
            mock_settings.mirofish_timeout = 30
            mock_settings.mirofish_max_retries = 3
            c = make_mirofish_client()
        assert c.mode == "mock"

    def test_factory_live_mode(self):
        with patch("app.config.settings") as mock_settings:
            mock_settings.mirofish_base_url = "http://mf:5001"
            mock_settings.mirofish_api_key = "key"
            mock_settings.mirofish_mode = "live"
            mock_settings.mirofish_fallback_to_mock = True
            mock_settings.mirofish_polling_interval = 2.0
            mock_settings.mirofish_max_polling = 150
            mock_settings.mirofish_timeout = 30
            mock_settings.mirofish_max_retries = 3
            c = make_mirofish_client()
        assert c.mode == "live"
        assert isinstance(c._adapter, MiroFishAdapter)


# ---------------------------------------------------------------------------
# 16. TestValidationRouteMode
# ---------------------------------------------------------------------------

class TestValidationRouteMode:
    def test_run_returns_validation_mode_field(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-test", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "validation_mode" in body

    def test_run_default_mode_is_mock(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-test", "prd": minimal_prd_dict},
        )
        body = resp.json()
        assert body["validation_mode"] == "mock"

    def test_run_mock_mode_job_is_none(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-test", "prd": minimal_prd_dict},
        )
        body = resp.json()
        # job is None in mock mode (no MiroFish HTTP involved)
        assert body["job"] is None

    def test_package_endpoint_has_no_validation_mode(self, client, minimal_prd_dict):
        """ValidationResponse on /package keeps defaults (validation_mode='mock', job=None)."""
        resp = client.post(
            "/validation/package",
            json={"project_id": "proj-test", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200
        # Fields exist with defaults even on /package (part of response model)
        body = resp.json()
        assert body.get("validation_mode") == "mock"
        assert body.get("job") is None


# ---------------------------------------------------------------------------
# 17. TestValidationRouteRegression
# ---------------------------------------------------------------------------

class TestValidationRouteRegression:
    """Regression: all existing /validation/run behaviours preserved after T10."""

    def test_status_is_still_completed(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-r", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_result_is_present(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-r", "prd": minimal_prd_dict},
        )
        body = resp.json()
        assert body["result"] is not None
        assert "summary" in body["result"]

    def test_schema_valid_is_true(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-r", "prd": minimal_prd_dict},
        )
        assert resp.json()["schema_valid"] is True

    def test_simulation_spec_present(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-r", "prd": minimal_prd_dict},
        )
        assert resp.json()["simulation_spec"] is not None

    def test_invalid_prd_returns_schema_invalid(self, client):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-r", "prd": {"bad": "prd"}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "schema_invalid"
        assert resp.json()["schema_valid"] is False

    def test_package_endpoint_unchanged(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/package",
            json={"project_id": "proj-r", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "packaged"
        assert body["result"] is None

    def test_schema_check_endpoint_unchanged(self, client, minimal_prd_dict):
        resp = client.post(
            "/validation/schema-check",
            json={"project_id": "proj-r", "prd": minimal_prd_dict},
        )
        assert resp.status_code == 200
        assert resp.json()["schema_valid"] is True

    def test_full_prd_result_fields_populated(self, client, full_prd_dict):
        resp = client.post(
            "/validation/run",
            json={"project_id": "proj-r", "prd": full_prd_dict},
        )
        body = resp.json()
        result = body["result"]
        assert isinstance(result["top_risks"], list)
        assert isinstance(result["missing_requirements"], list)
        assert isinstance(result["stakeholder_objections"], list)
        assert isinstance(result["recommended_questions"], list)


# ---------------------------------------------------------------------------
# 18. TestConfigT10Settings
# ---------------------------------------------------------------------------

class TestConfigT10Settings:
    def test_mirofish_mode_default_mock(self):
        s = Settings()
        assert s.mirofish_mode == "mock"

    def test_mirofish_timeout_default(self):
        s = Settings()
        assert s.mirofish_timeout == 30

    def test_mirofish_max_retries_default(self):
        s = Settings()
        assert s.mirofish_max_retries == 3

    def test_mirofish_polling_interval_default(self):
        s = Settings()
        assert s.mirofish_polling_interval == 2.0

    def test_mirofish_max_polling_default(self):
        s = Settings()
        assert s.mirofish_max_polling == 150

    def test_mirofish_fallback_to_mock_default_true(self):
        s = Settings()
        assert s.mirofish_fallback_to_mock is True

    def test_mirofish_base_url_default_5001(self):
        s = Settings()
        assert "5001" in s.mirofish_base_url

    def test_env_override_mode(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_MODE", "live")
        s = Settings()
        assert s.mirofish_mode == "live"

    def test_env_override_polling_interval(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_POLLING_INTERVAL", "5.0")
        s = Settings()
        assert s.mirofish_polling_interval == 5.0

    def test_env_override_fallback(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_FALLBACK_TO_MOCK", "false")
        s = Settings()
        assert s.mirofish_fallback_to_mock is False


# ---------------------------------------------------------------------------
# 19. TestBuildCreatePayload
# ---------------------------------------------------------------------------

class TestBuildCreatePayload:
    def test_payload_has_required_keys(self, sim_spec):
        payload = _build_create_payload(sim_spec)
        for key in ("project_id", "graph_id", "spec_id", "prd_summary",
                    "validation_config", "prd_markdown"):
            assert key in payload, f"Missing key: {key}"

    def test_spec_id_passed(self, sim_spec):
        payload = _build_create_payload(sim_spec)
        assert payload["spec_id"] == sim_spec.spec_id

    def test_validation_config_is_dict(self, sim_spec):
        payload = _build_create_payload(sim_spec)
        assert isinstance(payload["validation_config"], dict)

    def test_prd_markdown_is_string(self, sim_spec):
        payload = _build_create_payload(sim_spec)
        assert isinstance(payload["prd_markdown"], str)

    def test_prd_summary_is_dict(self, sim_spec):
        payload = _build_create_payload(sim_spec)
        assert isinstance(payload["prd_summary"], dict)
