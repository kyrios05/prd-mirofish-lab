"""
conftest.py — Shared pytest fixtures and path helpers for the API test suite.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture directory
# ---------------------------------------------------------------------------
FIXTURES_DIR: Path = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------
# Settings loads apps/api/.env (see Settings.model_config). That file holds the
# developer's local setup (MIROFISH_MODE=live, real API keys), which would make
# tests that assert *default* values fail depending on who runs them. Point the
# env_file at a path that does not exist and clear the matching env vars so the
# whole suite always sees pristine defaults.
_ISOLATED_ENV_PREFIXES = ("MIROFISH_", "OLLAMA_", "OPENAI_", "ANTHROPIC_", "LLM_")


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make Settings() deterministic: no .env file, no ambient provider vars."""
    from app.config import Settings, settings as live_settings
    from app.services import llm_provider

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in list(os.environ):
        if key.startswith(_ISOLATED_ENV_PREFIXES) or key == "DEBUG":
            monkeypatch.delenv(key, raising=False)

    # Clearing env only affects newly constructed Settings(); the already
    # imported singleton keeps whatever .env said. Tests must never reach a
    # real LLM, so force the deterministic mock-builder path on it too.
    # A test that wants the LLM path can re-enable it and mock the transport.
    monkeypatch.setattr(live_settings, "ollama_enabled", False, raising=False)
    llm_provider.reset_cache()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_fixture(filename: str) -> dict:
    """Load a JSON fixture file from tests/fixtures/ and strip _comment keys."""
    path = FIXTURES_DIR / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


# ---------------------------------------------------------------------------
# Pytest fixtures — valid payloads
# ---------------------------------------------------------------------------
@pytest.fixture
def minimal_prd() -> dict:
    """Load sample_prd_minimal.json as a plain dict."""
    return load_fixture("sample_prd_minimal.json")


@pytest.fixture
def full_prd() -> dict:
    """Load sample_prd_full.json as a plain dict."""
    return load_fixture("sample_prd_full.json")


# ---------------------------------------------------------------------------
# Pytest fixtures — invalid payloads
# ---------------------------------------------------------------------------
@pytest.fixture
def invalid_missing_required() -> dict:
    """Fixture with required top-level fields omitted (metadata, risks)."""
    return load_fixture("invalid_missing_required.json")


@pytest.fixture
def invalid_bad_enum() -> dict:
    """Fixture with invalid enum values (status, stage, feature priority)."""
    return load_fixture("invalid_bad_enum.json")


@pytest.fixture
def invalid_extra_field() -> dict:
    """Fixture with undeclared additional properties at root and nested level."""
    return load_fixture("invalid_extra_field.json")
