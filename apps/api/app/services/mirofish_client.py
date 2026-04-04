"""
services/mirofish_client.py — MiroFish simulation API client.

T10: Implements mode-switchable validation execution.

Mode behaviour
--------------
  mock (default, MIROFISH_MODE=mock)
      Delegates to run_mock_validation(spec) — same as T06.
      No external I/O.  All existing tests pass unchanged.

  live (MIROFISH_MODE=live)
      Delegates to MiroFishAdapter.run_full_lifecycle(spec).
      MiroFish server must be running (default port 5001).
      On adapter failure:
          - if fallback_to_mock=True  → falls back to run_mock_validation()
          - if fallback_to_mock=False → returns None

Signature (unchanged since T05)
--------------------------------
    run_validation(spec: SimulationSpec) -> ValidationResult | None

The run_validation() method now also returns a MiroFishJob | None so
that the validation route can include job metadata in the response.
Access via the job attribute after awaiting.
"""

from __future__ import annotations

import logging

from app.schemas import ValidationResult
from app.schemas.simulation import SimulationSpec
from app.services.mock_validation_engine import run_mock_validation
from app.services.mirofish_adapter import MiroFishAdapter, MiroFishJob

logger = logging.getLogger(__name__)


class MiroFishClient:
    """
    Client for the MiroFish simulation validation service.

    Parameters
    ----------
    base_url         : MiroFish server root URL.
    api_key          : Bearer token / X-API-Key.
    mode             : "mock" or "live" (default "mock").
    fallback_to_mock : If True and live mode fails, fall back to mock.
    polling_interval : Seconds between live-mode polling attempts.
    max_polling      : Cap on polling attempts before timeout.
    timeout          : Per-HTTP-request timeout in seconds.
    max_retries      : Max retry attempts per HTTP call.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        mode: str = "mock",
        fallback_to_mock: bool = True,
        polling_interval: float = 2.0,
        max_polling: int = 150,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.mode = mode.lower()
        self.fallback_to_mock = fallback_to_mock

        # Lazily built; only used in live mode
        self._adapter: MiroFishAdapter | None = None
        if self.mode == "live":
            self._adapter = MiroFishAdapter(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
                polling_interval=polling_interval,
                max_polling_attempts=max_polling,
            )

        # Last job metadata (populated after a live-mode call)
        self.last_job: MiroFishJob | None = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def run_validation(
        self, spec: SimulationSpec
    ) -> ValidationResult | None:
        """
        Run validation against a SimulationSpec and return a ValidationResult.

        mock mode  → run_mock_validation(spec)  (no I/O, deterministic)
        live mode  → MiroFishAdapter.run_full_lifecycle(spec)
                     Fallback to mock on failure if fallback_to_mock=True.

        Side-effects
        ------------
        Sets self.last_job after a live-mode call (None in mock mode).
        """
        self.last_job = None

        if self.mode == "live" and self._adapter is not None:
            return await self._run_live(spec)

        # Default: mock
        logger.debug("MiroFishClient mode=mock; delegating to run_mock_validation")
        return run_mock_validation(spec)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _run_live(self, spec: SimulationSpec) -> ValidationResult | None:
        """Execute the live MiroFishAdapter pipeline with optional mock fallback."""
        assert self._adapter is not None  # guaranteed by __init__

        logger.info(
            "MiroFishClient mode=live; starting adapter lifecycle for spec_id=%s",
            spec.spec_id,
        )
        try:
            # Submit + poll + fetch result (full lifecycle)
            result = await self._adapter.run_full_lifecycle(spec)

            # Capture job metadata from the adapter's last submit call
            # (adapter exposes its internal job tracking via the returned value)
            # We reconstruct a lightweight job record for the response layer.
            self.last_job = _make_sentinel_job(spec, result)

            if result is not None:
                logger.info(
                    "MiroFishClient live mode succeeded for spec_id=%s", spec.spec_id
                )
                return result

            # Adapter returned None — mapping failed or pipeline aborted
            logger.warning(
                "MiroFishClient live mode returned None for spec_id=%s; "
                "fallback_to_mock=%s",
                spec.spec_id,
                self.fallback_to_mock,
            )
        except Exception as exc:
            logger.error(
                "MiroFishClient live mode raised exception for spec_id=%s: %s; "
                "fallback_to_mock=%s",
                spec.spec_id,
                exc,
                self.fallback_to_mock,
            )
            self.last_job = _make_sentinel_job(spec, None, error=str(exc))

        # Fallback decision
        if self.fallback_to_mock:
            logger.info(
                "MiroFishClient falling back to mock engine for spec_id=%s",
                spec.spec_id,
            )
            return run_mock_validation(spec)

        return None


# ---------------------------------------------------------------------------
# Singleton factory (mirrors config settings)
# ---------------------------------------------------------------------------

def make_mirofish_client() -> MiroFishClient:
    """
    Create a MiroFishClient configured from app.config.settings.

    Imported and called by routes that need a client.  Using a factory
    (rather than a module-level singleton) makes tests easier to isolate.
    """
    from app.config import settings  # local import avoids circular at module load

    return MiroFishClient(
        base_url=settings.mirofish_base_url,
        api_key=settings.mirofish_api_key,
        mode=settings.mirofish_mode,
        fallback_to_mock=settings.mirofish_fallback_to_mock,
        polling_interval=settings.mirofish_polling_interval,
        max_polling=settings.mirofish_max_polling,
        timeout=settings.mirofish_timeout,
        max_retries=settings.mirofish_max_retries,
    )


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _make_sentinel_job(
    spec: SimulationSpec,
    result: ValidationResult | None,
    error: str | None = None,
) -> MiroFishJob:
    """
    Build a MiroFishJob record that summarises a completed (or failed) live run.

    Used so the validation route can include job metadata in its response
    even when the adapter doesn't surface its internal job object directly.
    """
    from app.services.mirofish_adapter import MiroFishJobStatus

    job = MiroFishJob()
    if result is not None:
        job._update(status=MiroFishJobStatus.COMPLETED, progress=1.0)
        job.result = result
    else:
        job._update(
            status=MiroFishJobStatus.FAILED,
            error=error or "adapter returned None result",
        )
    return job
