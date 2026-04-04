"""
services/mirofish_adapter.py — MiroFish async HTTP adapter (T10).

Wraps the multi-step MiroFish simulation API into a single clean coroutine:
    MiroFishAdapter.run_full_lifecycle(spec) -> ValidationResult | None

MiroFish API sequence
---------------------
  POST /api/simulation/create        → { simulation_id, status: "created" }
  POST /api/simulation/prepare       → { task_id, status: "preparing" }
  POST /api/simulation/prepare/status
       { task_id }                   → { status, progress }   ← poll until "ready"
  POST /api/simulation/{id}/run      → { status }             (async start)
  GET  /api/simulation/{id}          → { status, ... }        ← poll until "completed"
  GET  /api/simulation/{id}/report   → raw result dict

Lifecycle states
----------------
  CREATED → PREPARING → READY → RUNNING → COMPLETED
                                         ↓ (any step)
                                        FAILED

Design constraints
------------------
  - httpx.AsyncClient (no new HTTP library)
  - Exponential backoff on 5xx / network errors (max_retries)
  - Graceful degradation: mapping failure → None (caller falls back to mock)
  - mock_validation_engine is the fallback; this module does NOT import it.
    The fallback decision lives in MiroFishClient.
  - No schema changes: ValidationResult is used read-only from schemas.

Scope guard
-----------
  - mock_validation_engine.py : NOT imported here (T06, frozen)
  - SimulationSpec / ValidationResult schemas : NOT modified
  - validation_packager / markdown_renderer / mock_prd_builder : NOT touched
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from app.schemas import ValidationResult
from app.schemas.simulation import SimulationSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MiroFish Job Lifecycle Model
# ---------------------------------------------------------------------------

class MiroFishJobStatus(str, Enum):
    """Possible states of a MiroFish simulation job."""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MiroFishJob:
    """
    Internal tracking record for a single MiroFish simulation run.

    Fields
    ------
    job_id          : Internal UUID (assigned at submit time).
    simulation_id   : MiroFish-assigned simulation identifier (after /create).
    task_id         : MiroFish prepare task identifier (after /prepare).
    status          : Current lifecycle phase.
    progress        : 0.0–1.0 progress estimate; updated during polling.
    created_at      : ISO-8601 UTC creation timestamp.
    updated_at      : ISO-8601 UTC last-update timestamp.
    error           : Human-readable error message on FAILED; None otherwise.
    result          : Populated by get_result() on COMPLETED; None otherwise.
    """
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    simulation_id: str | None = None
    task_id: str | None = None
    status: MiroFishJobStatus = MiroFishJobStatus.CREATED
    progress: float = 0.0
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())
    error: str | None = None
    result: ValidationResult | None = None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (used in ValidationResponse.job field)."""
        return {
            "job_id": self.job_id,
            "simulation_id": self.simulation_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    def _update(
        self,
        status: MiroFishJobStatus | None = None,
        progress: float | None = None,
        error: str | None = None,
    ) -> None:
        """Mutate status/progress/error and refresh updated_at."""
        if status is not None:
            self.status = status
        if progress is not None:
            self.progress = progress
        if error is not None:
            self.error = error
        self.updated_at = _now_iso()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Response mapper
# ---------------------------------------------------------------------------

def _map_mirofish_response(
    raw: dict[str, Any],
    spec: SimulationSpec,
) -> ValidationResult | None:
    """
    Map a raw MiroFish report dict to a ValidationResult.

    MiroFish report keys (best-effort mapping — field names may vary):
      summary          → summary
      risks / top_risks                 → top_risks
      gaps / missing_requirements       → missing_requirements
      objections / stakeholder_objections → stakeholder_objections
      scope_adjustments                 → scope_adjustments
      questions / recommended_questions  → recommended_questions
      suggestions / rewrite_suggestions → rewrite_suggestions

    Returns None if the raw dict is completely unusable (e.g. not a dict).
    Falls back to empty lists for missing array fields.
    Always produces a non-empty summary.
    """
    if not isinstance(raw, dict):
        logger.warning("MiroFish report is not a dict (got %s); mapper returning None", type(raw))
        return None

    def _str_list(val: Any, *fallback_keys: str) -> list[str]:
        """Extract a list[str] from val or try fallback_keys in the raw dict."""
        if isinstance(val, list):
            return [str(item) for item in val if item]
        for key in fallback_keys:
            candidate = raw.get(key)
            if isinstance(candidate, list):
                return [str(item) for item in candidate if item]
        return []

    # Summary — mandatory; derive fallback from product name in spec
    summary_raw = raw.get("summary") or raw.get("overview") or raw.get("description")
    if summary_raw and isinstance(summary_raw, str) and summary_raw.strip():
        summary = summary_raw.strip()
    else:
        product_name = (
            spec.prd_summary.get("name")
            or spec.prd_summary.get("one_liner")
            or "this product"
        )
        summary = (
            f"MiroFish simulation completed for {product_name}. "
            "Review the sections below for detailed findings."
        )

    try:
        result = ValidationResult(
            summary=summary,
            top_risks=_str_list(raw.get("top_risks"), "risks", "risk_items"),
            missing_requirements=_str_list(
                raw.get("missing_requirements"), "gaps", "requirement_gaps"
            ),
            stakeholder_objections=_str_list(
                raw.get("stakeholder_objections"), "objections"
            ),
            scope_adjustments=_str_list(
                raw.get("scope_adjustments"), "adjustments", "scope_changes"
            ),
            recommended_questions=_str_list(
                raw.get("recommended_questions"), "questions", "open_questions"
            ),
            rewrite_suggestions=_str_list(
                raw.get("rewrite_suggestions"), "suggestions", "rewrites"
            ),
        )
        return result
    except Exception as exc:
        logger.error("Failed to construct ValidationResult from MiroFish report: %s", exc)
        return None


# ---------------------------------------------------------------------------
# MiroFish Async Adapter
# ---------------------------------------------------------------------------

class MiroFishAdapter:
    """
    Async adapter for the MiroFish multi-step simulation API.

    Usage (live mode)
    -----------------
        adapter = MiroFishAdapter(base_url="http://localhost:5001", api_key="...")
        result = await adapter.run_full_lifecycle(spec)

    The full lifecycle runs:
        submit_validation()  →  MiroFishJob (RUNNING state)
        poll_until_complete() →  MiroFishJob (COMPLETED state)
        get_result()          →  ValidationResult | None

    Parameters
    ----------
    base_url             : MiroFish server root URL (no trailing slash).
    api_key              : API key sent as ``X-API-Key`` header.
    timeout              : Per-request timeout in seconds.
    max_retries          : Maximum retry attempts per HTTP call.
    polling_interval     : Seconds to wait between polling attempts.
    max_polling_attempts : Total polling cap before FAILED/timeout.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5001",
        api_key: str = "",
        timeout: int = 30,
        max_retries: int = 3,
        polling_interval: float = 2.0,
        max_polling_attempts: int = 150,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.polling_interval = polling_interval
        self.max_polling_attempts = max_polling_attempts

    # -----------------------------------------------------------------------
    # HTTP helpers
    # -----------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def _post(
        self,
        client: httpx.AsyncClient,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        POST to ``self.base_url + path`` with exponential backoff retry.

        Raises
        ------
        httpx.HTTPError | httpx.RequestError on final failure.
        """
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await client.post(
                    url,
                    json=json_body or {},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                logger.info("POST %s → %s", path, resp.status_code)
                return data
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "POST %s attempt %d/%d failed: %s; retrying in %ds",
                    path, attempt + 1, self.max_retries, exc, wait,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
    ) -> dict[str, Any]:
        """
        GET ``self.base_url + path`` with exponential backoff retry.
        """
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await client.get(
                    url,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                logger.info("GET %s → %s", path, resp.status_code)
                return data
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "GET %s attempt %d/%d failed: %s; retrying in %ds",
                    path, attempt + 1, self.max_retries, exc, wait,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    # -----------------------------------------------------------------------
    # Step 1 + 2 + prepare-poll: submit_validation
    # -----------------------------------------------------------------------

    async def submit_validation(self, spec: SimulationSpec) -> MiroFishJob:
        """
        Drive the MiroFish API through create → prepare → prepare-poll → run.

        Returns a MiroFishJob in RUNNING state on success, or FAILED on error.

        Steps
        -----
        1. POST /api/simulation/create
        2. POST /api/simulation/prepare
        3. Poll POST /api/simulation/prepare/status until status == "ready"
        4. POST /api/simulation/{simulation_id}/run
        """
        job = MiroFishJob()
        logger.info("[job=%s] Starting submit_validation", job.job_id)

        async with httpx.AsyncClient() as client:
            # ── Step 1: create ──────────────────────────────────────────────
            try:
                create_payload = _build_create_payload(spec)
                create_resp = await self._post(
                    client, "/api/simulation/create", create_payload
                )
                simulation_id = (
                    create_resp.get("simulation_id")
                    or create_resp.get("id")
                    or create_resp.get("simulationId")
                )
                if not simulation_id:
                    raise ValueError(
                        f"create response missing simulation_id: {create_resp}"
                    )
                job.simulation_id = str(simulation_id)
                job._update(status=MiroFishJobStatus.PREPARING, progress=0.1)
                logger.info("[job=%s] Created simulation_id=%s", job.job_id, job.simulation_id)
            except Exception as exc:
                job._update(status=MiroFishJobStatus.FAILED, error=f"create failed: {exc}")
                logger.error("[job=%s] create step failed: %s", job.job_id, exc)
                return job

            # ── Step 2: prepare ─────────────────────────────────────────────
            try:
                prepare_resp = await self._post(
                    client,
                    "/api/simulation/prepare",
                    {"simulation_id": job.simulation_id},
                )
                task_id = (
                    prepare_resp.get("task_id")
                    or prepare_resp.get("taskId")
                    or prepare_resp.get("id")
                )
                if task_id:
                    job.task_id = str(task_id)
                job._update(progress=0.2)
                logger.info("[job=%s] Prepare started task_id=%s", job.job_id, job.task_id)
            except Exception as exc:
                job._update(status=MiroFishJobStatus.FAILED, error=f"prepare failed: {exc}")
                logger.error("[job=%s] prepare step failed: %s", job.job_id, exc)
                return job

            # ── Step 3: poll prepare/status ─────────────────────────────────
            try:
                job = await self._poll_prepare_status(client, job)
                if job.status == MiroFishJobStatus.FAILED:
                    return job
            except Exception as exc:
                job._update(
                    status=MiroFishJobStatus.FAILED,
                    error=f"prepare polling failed: {exc}",
                )
                logger.error("[job=%s] prepare poll failed: %s", job.job_id, exc)
                return job

            # ── Step 4: run ─────────────────────────────────────────────────
            try:
                await self._post(
                    client,
                    f"/api/simulation/{job.simulation_id}/run",
                    {},
                )
                job._update(status=MiroFishJobStatus.RUNNING, progress=0.5)
                logger.info("[job=%s] Simulation run started", job.job_id)
            except Exception as exc:
                job._update(status=MiroFishJobStatus.FAILED, error=f"run failed: {exc}")
                logger.error("[job=%s] run step failed: %s", job.job_id, exc)
                return job

        return job

    async def _poll_prepare_status(
        self,
        client: httpx.AsyncClient,
        job: MiroFishJob,
    ) -> MiroFishJob:
        """
        Poll POST /api/simulation/prepare/status until status is 'ready'.
        Updates job.progress along the way.
        """
        for attempt in range(self.max_polling_attempts):
            try:
                payload: dict[str, Any] = {}
                if job.task_id:
                    payload["task_id"] = job.task_id
                if job.simulation_id:
                    payload["simulation_id"] = job.simulation_id

                status_resp = await self._post(
                    client, "/api/simulation/prepare/status", payload
                )
                status_val = str(
                    status_resp.get("status") or status_resp.get("state") or ""
                ).lower()
                raw_progress = status_resp.get("progress")
                if isinstance(raw_progress, (int, float)):
                    job._update(progress=min(0.2 + float(raw_progress) * 0.3, 0.49))

                logger.debug(
                    "[job=%s] prepare/status attempt=%d status=%s",
                    job.job_id, attempt, status_val,
                )

                if status_val in ("ready", "completed", "done"):
                    job._update(status=MiroFishJobStatus.READY, progress=0.5)
                    return job
                if status_val in ("failed", "error"):
                    err = status_resp.get("error") or status_resp.get("message") or "prepare failed"
                    job._update(status=MiroFishJobStatus.FAILED, error=str(err))
                    return job

                await asyncio.sleep(self.polling_interval)
            except Exception as exc:
                logger.warning(
                    "[job=%s] prepare/status poll error (attempt %d): %s",
                    job.job_id, attempt, exc,
                )
                await asyncio.sleep(self.polling_interval)

        job._update(
            status=MiroFishJobStatus.FAILED,
            error=f"prepare polling timed out after {self.max_polling_attempts} attempts",
        )
        return job

    # -----------------------------------------------------------------------
    # Step 5: poll_until_complete
    # -----------------------------------------------------------------------

    async def poll_until_complete(self, job: MiroFishJob) -> MiroFishJob:
        """
        Poll GET /api/simulation/{id} until status reaches 'completed' or 'failed'.

        Mutates and returns the job record.
        """
        if not job.simulation_id:
            job._update(
                status=MiroFishJobStatus.FAILED,
                error="poll_until_complete called without simulation_id",
            )
            return job

        logger.info("[job=%s] Polling simulation %s", job.job_id, job.simulation_id)

        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_polling_attempts):
                try:
                    sim_data = await self._get(
                        client, f"/api/simulation/{job.simulation_id}"
                    )
                    status_val = str(
                        sim_data.get("status") or sim_data.get("state") or ""
                    ).lower()
                    raw_progress = sim_data.get("progress")
                    if isinstance(raw_progress, (int, float)):
                        job._update(progress=0.5 + float(raw_progress) * 0.4)

                    logger.debug(
                        "[job=%s] poll attempt=%d status=%s",
                        job.job_id, attempt, status_val,
                    )

                    if status_val in ("completed", "done", "success"):
                        job._update(status=MiroFishJobStatus.COMPLETED, progress=1.0)
                        logger.info("[job=%s] Simulation completed", job.job_id)
                        return job
                    if status_val in ("failed", "error", "cancelled"):
                        err = sim_data.get("error") or sim_data.get("message") or "simulation failed"
                        job._update(status=MiroFishJobStatus.FAILED, error=str(err))
                        logger.error("[job=%s] Simulation failed: %s", job.job_id, err)
                        return job

                    await asyncio.sleep(self.polling_interval)
                except Exception as exc:
                    logger.warning(
                        "[job=%s] poll error (attempt %d): %s",
                        job.job_id, attempt, exc,
                    )
                    await asyncio.sleep(self.polling_interval)

        job._update(
            status=MiroFishJobStatus.FAILED,
            error=f"simulation polling timed out after {self.max_polling_attempts} attempts",
        )
        logger.error("[job=%s] Polling timed out", job.job_id)
        return job

    # -----------------------------------------------------------------------
    # Step 6: get_result
    # -----------------------------------------------------------------------

    async def get_result(
        self, job: MiroFishJob, spec: SimulationSpec
    ) -> ValidationResult | None:
        """
        Fetch GET /api/simulation/{id}/report and map to ValidationResult.

        Returns None (not raises) if the report cannot be retrieved or mapped.
        """
        if job.status != MiroFishJobStatus.COMPLETED or not job.simulation_id:
            logger.warning(
                "[job=%s] get_result called in unexpected state %s",
                job.job_id, job.status,
            )
            return None

        async with httpx.AsyncClient() as client:
            try:
                report = await self._get(
                    client, f"/api/simulation/{job.simulation_id}/report"
                )
                result = _map_mirofish_response(report, spec)
                if result is None:
                    logger.warning(
                        "[job=%s] _map_mirofish_response returned None; caller should fallback",
                        job.job_id,
                    )
                else:
                    job.result = result
                    logger.info("[job=%s] Result mapped successfully", job.job_id)
                return result
            except Exception as exc:
                logger.error("[job=%s] get_result failed: %s", job.job_id, exc)
                return None

    # -----------------------------------------------------------------------
    # Full lifecycle (single entry point)
    # -----------------------------------------------------------------------

    async def run_full_lifecycle(
        self, spec: SimulationSpec
    ) -> ValidationResult | None:
        """
        Execute the complete MiroFish validation pipeline end-to-end.

        Sequence
        --------
        1. submit_validation(spec)    → job (RUNNING)
        2. poll_until_complete(job)   → job (COMPLETED | FAILED)
        3. get_result(job, spec)      → ValidationResult | None

        Returns None on any failure; the caller (MiroFishClient) is
        responsible for deciding whether to fall back to mock.
        """
        logger.info("run_full_lifecycle starting for spec_id=%s", spec.spec_id)

        job = await self.submit_validation(spec)
        if job.status == MiroFishJobStatus.FAILED:
            logger.error(
                "run_full_lifecycle: submit failed (job=%s): %s",
                job.job_id, job.error,
            )
            return None

        job = await self.poll_until_complete(job)
        if job.status != MiroFishJobStatus.COMPLETED:
            logger.error(
                "run_full_lifecycle: simulation did not complete (job=%s): %s",
                job.job_id, job.error,
            )
            return None

        result = await self.get_result(job, spec)
        if result is None:
            logger.warning(
                "run_full_lifecycle: result mapping returned None (job=%s); "
                "caller should fallback to mock",
                job.job_id,
            )
        return result


# ---------------------------------------------------------------------------
# Internal payload builder
# ---------------------------------------------------------------------------

def _build_create_payload(spec: SimulationSpec) -> dict[str, Any]:
    """
    Build the POST /api/simulation/create request body from a SimulationSpec.

    MiroFish expects: project_id, graph_id (or simulation config).
    We pass the full validation_config dict so MiroFish can interpret goals
    and personas without additional mapping on the adapter side.
    """
    return {
        "project_id": spec.prd_summary.get("project_id") or spec.spec_id,
        "graph_id": spec.prd_summary.get("category") or "prd_validation",
        "spec_id": spec.spec_id,
        "prd_summary": spec.prd_summary,
        "validation_config": spec.validation_config.model_dump(),
        "prd_markdown": spec.prd_markdown,
    }
