"""
models.py — Compatibility shim.

All domain models have been moved to app.schemas (T01 refactor).
This file re-exports everything from schemas so that any existing code
that imports from app.models continues to work without modification.

TODO(T03): Remove this file once all route/service imports are updated
           to use `from app.schemas import ...` directly.
"""

# Re-export everything from the new schemas package
from app.schemas import *  # noqa: F401, F403
from app.schemas import __all__  # noqa: F401
