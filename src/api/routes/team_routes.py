"""
Simple team training routes for collaborative features.
Stores lightweight data in data/teams.json (JSON store) for now.
"""
import json
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from infrastructure.settings import PROJECT_ROOT

router = APIRouter(prefix="/api/team", tags=["team"])  # unified

_STORE = PROJECT_ROOT / "data" / "teams.json"


def _load() -> Dict[str, Any]:
    if _STORE.exists():
        try:
            return json.loads(_STORE.read_text(encoding="utf-8"))
        except Exception:
            return {"teams": {}}
    return {"teams": {}}


def _save(obj: Dict[str, Any]):
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(obj, indent=2), encoding="utf-8")


@router.post("/create")
async def create_team(payload: Dict[str, Any]) -> Dict[str, Any]:
    team_id = (payload or {}).get("team_id")
    name = (payload or {}).get("name", "Team")
    if not team_id:
        raise HTTPException(status_code=400, detail="team_id is required")
    store = _load()
    if team_id in store["teams"]:
        raise HTTPException(status_code=409, detail="team already exists")
    store["teams"][team_id] = {"team_id": team_id, "name": name, "members": [], "sessions": []}
    _save(store)
    return {"success": True, "team": store["teams"][team_id]}


@router.post("/members/add")
async def add_member(payload: Dict[str, Any]) -> Dict[str, Any]:
    team_id = (payload or {}).get("team_id")
    user_id = (payload or {}).get("user_id")
    if not team_id or not user_id:
        raise HTTPException(status_code=400, detail="team_id and user_id required")
    store = _load()
    team = store["teams"].get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")
    if user_id not in team["members"]:
        team["members"].append(user_id)
    _save(store)
    return {"success": True, "team": team}


@router.post("/session/record")
async def record_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    team_id = (payload or {}).get("team_id")
    user_id = (payload or {}).get("user_id")
    session_id = (payload or {}).get("session_id")
    score = (payload or {}).get("score")
    if not all([team_id, user_id, session_id]):
        raise HTTPException(status_code=400, detail="team_id, user_id, session_id required")
    store = _load()
    team = store["teams"].get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")
    team["sessions"].append({"user_id": user_id, "session_id": session_id, "score": score})
    _save(store)
    return {"success": True}


@router.get("/{team_id}/dashboard")
async def team_dashboard(team_id: str) -> Dict[str, Any]:
    store = _load()
    team = store["teams"].get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")
    member_count = len(team["members"]) or 1
    sessions = team["sessions"]
    avg_score = (
        sum([s.get("score", 0) or 0 for s in sessions]) / max(len(sessions), 1)
        if sessions
        else 0
    )
    return {
        "team": {"team_id": team_id, "name": team.get("name")},
        "members": team["members"],
        "summary": {
            "total_sessions": len(sessions),
            "avg_sessions_per_member": len(sessions) / member_count,
            "average_score": round(avg_score, 2),
        },
        "recent_sessions": sessions[-10:],
    }
