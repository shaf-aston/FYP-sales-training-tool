"""A real prospect's line for the buyer's move, from config/prospect_lines.yaml: no AI.

pick_line(move, seller_line, persona, history, embed, seed) gives the line to say, or None when none fits (the AI
then words the move). Lines for the move and topic are filled from the persona ({need}, {pain}, {budget}), never
said twice in a call, and ranked by meaning against the seller's line with the shared embedder; an answer (`share`)
must be at least `moves.min_score` close, so "What's your budget?" never gets a line about their goals. The pick
among the closest few is seeded by session and turn: the same session replays the same way.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable

from core.infra.loader import load_buyer_config, load_yaml
from core.infra.similarity import similarity
from core.sell_mode.buyer_moves import Move

Embed = Callable[[list[str]], object]

_BLANK = re.compile(r"\{(need|pain|budget|budget_kind)\}")
TOP = 3   # the pick is among this many closest lines, so two sessions on the same path still differ
MIN_SCORE = load_buyer_config()["moves"]["min_score"]   # an answer's line must be this close (buyer.yaml moves)


def lines_for(move: Move) -> list[str]:
    """The bank's lines for a move: its topic's, or (for anything but an answer) its general ones."""
    bank = load_yaml("prospect_lines.yaml")["lines"].get(move.kind, {})
    if move.topic in bank:
        return list(bank[move.topic])
    return [] if move.kind == "share" else list(bank.get("general", []))


def _said(history: list[dict]) -> str:
    return " ".join(m.get("content", "") for m in history if m.get("role") == "assistant").lower()


def _next_unsaid(items: list, said: str) -> str | None:
    """The persona's first need (or pain) not said yet in this call: they open up one thing at a time."""
    for item in items or []:
        text = str(item).strip()
        if text and text.lower() not in said:
            return text
    return None


def _sentence_case(text: str) -> str:
    """Capitals where a filled blank starts a sentence: "{need}, mostly." -> "Cost reduction, mostly."."""
    return re.sub(r"(^|[.?!]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def fill(line: str, persona: dict, said: str) -> str | None:
    """The line with the persona's words in its blanks, or None when one cannot be filled."""
    budget = str(persona.get("budget") or "").strip()
    figure = any(ch.isdigit() for ch in budget)
    values = {
        "need": _next_unsaid(persona.get("needs", []), said),
        "pain": _next_unsaid(persona.get("pain_points", []), said),
        "budget": budget if figure else None,             # "$50,000-$70,000"
        "budget_kind": budget if budget and not figure else None,   # "cost-conscious", "mid-range"
    }
    if any(values[name] is None for name in _BLANK.findall(line)):
        return None
    return _sentence_case(_BLANK.sub(lambda m: values[m.group(1)], line))


def pick_line(move: Move, seller_line: str, persona: dict, history: list[dict], embed: Embed | None,
              seed: str) -> str | None:
    """The line to say for `move`, or None when the bank has none that fits."""
    said = _said(history)
    candidates: list[str] = []
    for line in lines_for(move):
        text = fill(line, persona, said)
        if text and text.lower() not in said and text not in candidates:
            candidates.append(text)
    if not candidates:
        return None
    rng = random.Random(seed)
    if embed is None or not (seller_line or "").strip():
        return rng.choice(candidates)
    scores = similarity([seller_line], candidates, embed)[0]
    ranked = sorted(zip(scores, candidates), key=lambda sc: -sc[0])
    if move.kind == "share" and ranked[0][0] < MIN_SCORE:
        return None
    return rng.choice([text for _, text in ranked[:TOP]])
