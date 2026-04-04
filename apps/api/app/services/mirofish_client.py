"""
services/mirofish_client.py — MiroFish simulation API client.

Current state: Stub client.  Signature updated in T05 to accept SimulationSpec
instead of PRDDocument.  Actual HTTP calls and response mapping are T10 scope.

Signature change (T05)
----------------------
Before: run_validation(prd: PRDDocument) -> ValidationResult | None
After:  run_validation(spec: SimulationSpec) -> ValidationResult | None

Rationale: MiroFish receives the fully-packaged SimulationSpec (with
prd_markdown, validation_config, focus_areas) rather than a raw PRDDocument.
The packaging step (validation_packager.py) is now cleanly separated from
the HTTP transport layer.

NOTE(T10): Implement run_validation() — add HTTP client, auth, retry/backoff.
NOTE(T06): Add MiroFish-specific response adapter (ValidationResult mapping).
"""

from __future__ import annotations

from app.schemas import ValidationResult
from app.schemas.simulation import SimulationSpec


class MiroFishClient:
    """
    Client for the MiroFish simulation validation service.
    TODO(T10): Implement actual HTTP client with retry/backoff.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    async def run_validation(
        self, spec: SimulationSpec
    ) -> ValidationResult | None:
        """
        Send a SimulationSpec to MiroFish and return the ValidationResult.

        Parameters
        ----------
        spec : SimulationSpec
            Produced by validation_packager.package_for_simulation().
            Contains the full PRD, Markdown rendering, and validation config.

        Returns
        -------
        ValidationResult | None
            Populated by T10/T06 once the MiroFish HTTP call is implemented.
            Currently always returns None (stub).

        TODO(T10): POST spec.model_dump() to {self.base_url}/simulate
        TODO(T10): Handle auth header: Authorization: Bearer {self.api_key}
        TODO(T10): Map JSON response → ValidationResult via T06 adapter.
        """
        return None
