"""
services/mirofish_client.py — MiroFish simulation API client.

Current state (T06): Stub client wired to mock_validation_engine.
  - run_validation() now returns a ValidationResult from the mock engine
    instead of returning None.
  - Actual HTTP call to MiroFish is T10 scope.

Signature (unchanged since T05)
--------------------------------
    run_validation(spec: SimulationSpec) -> ValidationResult | None

T06 change
----------
Before: always returns None (T05 stub)
After:  returns run_mock_validation(spec) for end-to-end demo support

TODO(T10): Replace mock engine call with real HTTP POST to MiroFish API.
TODO(T10): Add auth header: Authorization: Bearer {self.api_key}
TODO(T10): Map JSON response → ValidationResult via T06 adapter.
NOTE(T06): mock_validation_engine.run_mock_validation is the drop-in
           prototype for the real response adapter (T10).
"""

from __future__ import annotations

from app.schemas import ValidationResult
from app.schemas.simulation import SimulationSpec
from app.services.mock_validation_engine import run_mock_validation


class MiroFishClient:
    """
    Client for the MiroFish simulation validation service.

    T06: Internally calls run_mock_validation() to produce a deterministic,
         content-aware ValidationResult for end-to-end demo purposes.
    TODO(T10): Implement actual HTTP client with retry/backoff.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    async def run_validation(
        self, spec: SimulationSpec
    ) -> ValidationResult | None:
        """
        Run validation against a SimulationSpec and return a ValidationResult.

        Parameters
        ----------
        spec : SimulationSpec
            Produced by validation_packager.package_for_simulation().
            Contains the full PRD, Markdown rendering, and validation config.

        Returns
        -------
        ValidationResult
            Content-aware result produced by run_mock_validation() (T06).
            TODO(T10): Replace with real MiroFish HTTP response.

        Current behaviour (T06)
        -----------------------
        Delegates to run_mock_validation(spec) — a pure function that derives
        all 7 ValidationResult fields from the PRD data inside spec.
        No HTTP calls, no LLM, no external I/O.

        T10 replacement stub
        --------------------
        # resp = await httpx.AsyncClient().post(
        #     f"{self.base_url}/simulate",
        #     json=spec.model_dump(),
        #     headers={"Authorization": f"Bearer {self.api_key}"},
        #     timeout=30,
        # )
        # resp.raise_for_status()
        # return ValidationResult.model_validate(resp.json())
        """
        # TODO(T10): replace with real HTTP call to self.base_url/simulate
        return run_mock_validation(spec)
