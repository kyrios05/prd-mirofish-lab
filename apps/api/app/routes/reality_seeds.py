"""Nemotron routes exclusively for PRD MiroFish Lab."""
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.schemas import RealitySeedRequest
from app.services import reality_seeds, state_db
from app.services.session_store import session_store

router = APIRouter(prefix="/simulation/reality-seeds", tags=["reality-seeds"])
logger = logging.getLogger(__name__)


@router.post("/nemotron")
async def nemotron_seeds(body: RealitySeedRequest):
    if session_store.get_session(body.session_id) is None:
        raise HTTPException(404, "Session not found")
    if settings.llm_provider != "openai" or not settings.ollama_enabled:
        raise HTTPException(409, "Nemotron adaptation requires the configured OpenAI Live provider")
    try:
        selection = await asyncio.wait_for(reality_seeds.generate_selection(body), timeout=settings.llm_timeout + 90)
    except Exception as error:
        logger.exception("PRD Lab Nemotron selection failed")
        raise HTTPException(502, "Nemotron 시드 조회 또는 페르소나 생성에 실패했습니다. 설정과 연결을 확인한 뒤 재시도해주세요.") from error
    return {"status": "success", "stakeholders": selection["stakeholders"], "selection_id": selection["selection_id"], "provenance": selection["provenance"], "members": [{"name": member["name"], "source_uuid": member["source_uuid"]} for member in selection["adapted_members"]]}


@router.get("/{selection_id}")
async def get_selection(selection_id: str, session_id: str):
    selection = state_db.load("reality-seed-selection", selection_id)
    if session_store.get_session(session_id) is None or not selection or selection["session_id"] != session_id:
        raise HTTPException(404, "Seed selection not found in this session")
    return selection
