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


@router.get("/ready")
async def readiness():
    """Readiness checks dependencies, separately from process liveness."""
    import httpx
    from fastapi.responses import JSONResponse
    from app.config import settings
    from app.services import state_db
    checks = {}
    try:
        with state_db.connect() as db:
            db.execute('SELECT 1')
        checks["storage"] = True
    except Exception:
        checks["storage"] = False
    checks["llm_configuration"] = not settings.ollama_enabled
    if settings.ollama_enabled:
        checks["llm_configuration"] = bool(
            settings.openai_api_key.strip() if settings.llm_provider == "openai"
            else settings.anthropic_api_key.strip() if settings.llm_provider == "claude"
            else settings.ollama_base_url
        )
    if settings.mirofish_mode == "live":
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f'{settings.mirofish_base_url.rstrip("/")}/health')
                response.raise_for_status()
            checks["mirofish"] = True
        except httpx.HTTPError:
            checks["mirofish"] = False
    ready = all(checks.values())
    return JSONResponse({"status": "ready" if ready else "not_ready", "checks": checks}, status_code=200 if ready else 503)
