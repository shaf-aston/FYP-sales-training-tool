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
    """The bank's lines for a move: its topic's, else (for anything but an answer) its yes/no ones for a yes/no
    question, else its general ones."""
    bank = load_yaml("prospect_lines.yaml")["lines"].get(move.kind, {})
    if move.topic in bank:
        return list(bank[move.topic])
    if move.kind == "share":
        return []
    return list(bank["closed"] if move.closed and "closed" in bank else bank.get("general", []))


def _said(history: list[dict]) -> str:
    return " ".join(m.get("content", "") for m in history if m.get("role") == "assistant").lower()


def _voice() -> dict:
    return load_yaml("prospect_lines.yaml")["voice"]


def spoken(item: str) -> str:
    """A need or pain as the buyer says it about themselves: "wife is worried about his health" -> "my wife is
    worried about my health", "doesn't know proper form" -> "I don't know proper form". Notes in brackets go."""
    voice = _voice()
    text = re.sub(r"\s*\([^)]*\)", "", str(item)).strip()
    first, _, rest = text.partition(" ")
    lowered = first.lower()
    if lowered in voice["starts"]:
        text = f"{voice['starts'][lowered]} {rest}".strip()
    elif lowered in voice["my"]:
        text = f"my {text}"
    for phrase in sorted(voice["replace"], key=len, reverse=True):
        text = re.sub(rf"(?<![\w']){re.escape(phrase)}(?![\w'])", voice["replace"][phrase], text, flags=re.IGNORECASE)
    return text


def is_clause(text: str) -> bool:
    """A whole clause ("my budget is fixed"), not a thing ("manual reporting")."""
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & set(_voice()["clause_words"]))


def _takes_clause(line: str, blank: str) -> bool:
    """Whether a clause reads right in this line's blank: starting a sentence, or after "is ", ", " or "but "."""
    at = line.index("{" + blank + "}")
    before = line[:at]
    return not before.strip() or before.rstrip().endswith((".", "?", "!")) or before.endswith(("is ", ", ", "but "))


def _next_unsaid(items: list, said: str) -> str | None:
    """The persona's first need (or pain) not said yet in this call, as they say it: they open up one thing at a time."""
    for item in items or []:
        text = spoken(str(item).strip())
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
    blanks = _BLANK.findall(line)
    if any(values[name] is None for name in blanks):
        return None
    if any(is_clause(values[name]) and not _takes_clause(line, name) for name in blanks if name in ("need", "pain")):
        return None   # "It's my budget is fixed, mostly."
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
