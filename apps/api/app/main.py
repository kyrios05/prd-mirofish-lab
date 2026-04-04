"""
main.py — FastAPI application entry point.

Startup order:
  1. Load settings (config.py)
  2. Register routers (routes/)
  3. Expose OpenAPI schema (includes all app.schemas models)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import chat, health, validation

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Chat-driven PRD generation and MiroFish validation API.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(validation.router)


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
