"""
conftest.py — Shared pytest fixtures and path helpers for the API test suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture directory
# ---------------------------------------------------------------------------
FIXTURES_DIR: Path = Path(__file__).parent / "fixtures"


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
