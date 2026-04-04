"""
services/mirofish_client.py — MiroFish simulation API client.

Current state: Stub client.
Actual HTTP calls and payload mapping is T05/T06 scope.

NOTE(T05): Implement run_validation() to package PRDDocument into
           MiroFish simulation spec and invoke the simulation API.
NOTE(T06): Add MiroFish-specific adapter logic (payload transform, auth).
"""

from __future__ import annotations

from app.schemas import PRDDocument, ValidationResult


class MiroFishClient:
    """
    Client for the MiroFish simulation validation service.
    TODO(T05/T06): Implement actual HTTP client with retry/backoff.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    async def run_validation(
        self, prd: PRDDocument
    ) -> ValidationResult | None:
        """
        Package a PRDDocument into a MiroFish simulation payload and
        invoke the validation API.
        TODO(T05): Implement packaging + HTTP call.
        TODO(T06): Add MiroFish-specific payload transform.
        """
        return None
