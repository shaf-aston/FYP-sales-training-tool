"""
Minimal external integration API with API-key header check.
Set env API_KEY to enable. Designed for safe read-only exposure initially.
"""
import os
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from services.persona_service import persona_service

router = APIRouter(prefix="/external", tags=["external"])  # not under /api to make it explicit


def _require_key(x_api_key: Optional[str]):
    required = os.environ.get("API_KEY")
    if not required:
        raise HTTPException(status_code=503, detail="External API disabled (missing API_KEY)")
    if x_api_key != required:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.get("/personas")
async def personas(x_api_key: Optional[str] = Header(default=None)):
    _require_key(x_api_key)
    return {"personas": persona_service.list_personas()}
