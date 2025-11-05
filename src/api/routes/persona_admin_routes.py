"""
Persona administration routes: clone personas from uploaded text and manage custom personas.
"""
import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

from services.ai_services import persona_service, Persona, PersonaType, DifficultyLevel

router = APIRouter(prefix="/api/personas", tags=["persona-admin"])  # under unified /api


# --- simple heuristic extractors -------------------------------------------------
BUDGET_KEYS = [
    (re.compile(r"\b(student|budget|cheap|afford|expensive|price|cost)\b", re.I), PersonaType.BUDGET_CONSCIOUS),
]
SKEPTIC_KEYS = [
    (re.compile(r"\b(skeptic|skeptical|proof|data|evidence|roi|results)\b", re.I), PersonaType.SKEPTICAL),
]
TIME_KEYS = [
    (re.compile(r"\b(time|busy|minutes|schedule|no time|limited)\b", re.I), PersonaType.TIME_CONSTRAINED),
]
HEALTH_KEYS = [
    (re.compile(r"\b(injury|safe|arthritis|back pain|health|age)\b", re.I), PersonaType.HEALTH_FOCUSED),
]


def _infer_age(text: str) -> int:
    m = re.search(r"\b(\d{2})\s*[-]?(?:year\s*old|yo)?\b", text, re.I)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 30
    return 30


def _infer_type(text: str) -> PersonaType:
    for patt, ptype in BUDGET_KEYS + SKEPTIC_KEYS + TIME_KEYS + HEALTH_KEYS:
        if patt.search(text):
            return ptype
    return PersonaType.BEGINNER


def _infer_difficulty(text: str) -> DifficultyLevel:
    # naive: skeptical/time mentions -> harder
    if any(p.search(text) for p, _ in SKEPTIC_KEYS + TIME_KEYS):
        return DifficultyLevel.MEDIUM
    return DifficultyLevel.EASY


def _split_list(text: str, fallback: Optional[List[str]] = None) -> List[str]:
    items = [i.strip() for i in re.split(r"[,;\n]+", text or "") if i.strip()]
    return items or (fallback or [])


# --- routes ---------------------------------------------------------------------

@router.post("/clone")
async def clone_persona(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a persona draft from uploaded text (not persisted unless save=true).
    Body: { name?: str, source_text: str, industry?: str, save?: bool }
    """
    text = (payload or {}).get("source_text", "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="source_text is required")

    name = (payload or {}).get("name", "CustomPersona")
    industry = (payload or {}).get("industry", "fitness")
    save = bool((payload or {}).get("save", False))

    persona_type = _infer_type(text)
    difficulty = _infer_difficulty(text)
    age = _infer_age(text)

    # Rough heuristics for goals/concerns/objections
    goals = _split_list(re.search(r"goals?\s*[:\-]\s*(.+)", text, re.I|re.S).group(1) if re.search(r"goals?\s*[:\-]\s*(.+)", text, re.I|re.S) else "")
    concerns = _split_list(re.search(r"concerns?\s*[:\-]\s*(.+)", text, re.I|re.S).group(1) if re.search(r"concerns?\s*[:\-]\s*(.+)", text, re.I|re.S) else "")
    objections = _split_list(re.search(r"objections?\s*[:\-]\s*(.+)", text, re.I|re.S).group(1) if re.search(r"objections?\s*[:\-]\s*(.+)", text, re.I|re.S) else "")

    persona = Persona(
        name=name,
        age=age,
        background=(text[:240] + "...") if len(text) > 240 else text,
        personality_traits=[persona_type.value],
        goals=goals or ["improve fitness", "learn more"],
        concerns=concerns or ["cost", "time"],
        objections=objections or ["too expensive", "no time"],
        budget_range="variable",
        decision_style="mixed",
        expertise_level="beginner",
        persona_type=persona_type,
        difficulty=difficulty,
        preferred_communication="friendly",
        industry=industry,
    )

    if save:
        persona_service.add_or_update_persona(persona, persist=True)

    return {"success": True, "saved": save, "persona": persona.to_dict()}


@router.post("/save")
async def save_persona(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a persona object previously drafted. Body: { persona: {...} }"""
    p = (payload or {}).get("persona")
    if not p:
        raise HTTPException(status_code=400, detail="persona object required")

    try:
        persona = Persona(
            name=p["name"],
            age=p.get("age", 30),
            background=p.get("background", ""),
            personality_traits=p.get("personality_traits", []),
            goals=p.get("goals", []),
            concerns=p.get("concerns", []),
            objections=p.get("objections", []),
            budget_range=p.get("budget_range", ""),
            decision_style=p.get("decision_style", ""),
            expertise_level=p.get("expertise_level", "beginner"),
            persona_type=PersonaType(p.get("persona_type", PersonaType.BEGINNER.value)),
            difficulty=DifficultyLevel(p.get("difficulty", DifficultyLevel.EASY.value)),
            health_considerations=p.get("health_considerations"),
            time_constraints=p.get("time_constraints"),
            preferred_communication=p.get("preferred_communication", "friendly"),
            industry=p.get("industry", "fitness"),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid persona: {e}")

    persona_service.add_or_update_persona(persona, persist=True)
    return {"success": True, "persona": persona.to_dict()}


@router.get("/custom")
async def list_custom_personas() -> Dict[str, Any]:
    # Heuristic: entries not in defaults are custom
    defaults = {"mary", "jake", "sarah", "david"}
    personas = [p for p in persona_service.list_personas() if p["name"].lower() not in defaults]
    return {"personas": personas}
