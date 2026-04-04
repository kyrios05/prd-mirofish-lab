"""
routes/health.py — Health check endpoint.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Returns service health status."""
    from app.config import settings

    return HealthResponse(status="ok", version=settings.app_version)
