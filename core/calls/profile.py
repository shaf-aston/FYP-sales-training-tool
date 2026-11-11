"""The prospect's profile, built from what they said in the call: the buyer a learner practises against.

Every field comes from config/calls.yaml patterns applied to the prospect's own sentences, and keeps its
evidence (the quotes or counts it came from), so the learner can see why the profile says what it says.
The profile's keys are a sell-mode persona's keys plus `objections`, `difficulty` and `evidence`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.calls.roles import Roles, count_questions
from core.calls.transcript import Turn, sentences

OBJECTION_TYPES = ("price", "skepticism", "timing", "partner", "fear")   # buyer.yaml concern types


@dataclass
class Profile:
    name: str
    background: str = ""
    personality: str = ""
    budget: str = ""
    needs: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)
    objections: list[dict] = field(default_factory=list)   # {"type", "text"}, their words
    difficulty: str = "medium"
    evidence: dict[str, list[str]] = field(default_factory=dict)


def _patterns(items: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in items]


def _hits(said: list[str], patterns: list[re.Pattern]) -> list[str]:
    """The sentences that match any pattern, in call order, without repeats."""
    seen, found = set(), []
    for sentence in said:
        key = sentence.lower()
        if key not in seen and any(p.search(sentence) for p in patterns):
            seen.add(key)
            found.append(sentence)
    return found


def _quote(sentence: str, cfg: dict) -> str:
    """A sentence kept as it was said, cut at a word boundary to the quote limit."""
    limit = cfg["limits"]["max_quote_chars"]
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def display_name(speaker: str, cfg: dict) -> str:
    """Their first name, or the fallback when the transcript only says "Speaker 2"."""
    if any(re.search(p, speaker.strip(), re.IGNORECASE) for p in cfg["anonymous_speakers"]):
        return cfg["fallback_name"]
    return speaker.split()[0]


def _objections(said: list[str], cfg: dict) -> list[dict]:
    """Their objections in their own words: at most `per_type` of a type and `max_objections` in all."""
    limits, found, per_type = cfg["limits"], [], {}
    patterns = {kind: _patterns(cfg["objections"][kind]) for kind in OBJECTION_TYPES}
    for sentence in said:
        for kind in OBJECTION_TYPES:
            if per_type.get(kind, 0) < limits["per_type"] and any(p.search(sentence) for p in patterns[kind]):
                found.append({"type": kind, "text": _quote(sentence, cfg)})
                per_type[kind] = per_type.get(kind, 0) + 1
                break   # one type per sentence: the first listed wins
        if len(found) >= limits["max_objections"]:
            break
    return found


def _stats(turns: list[Turn], said: list[str], cfg: dict) -> dict[str, float]:
    """How they talk: the numbers the difficulty and personality rules read."""
    words = sum(len(t.text.split()) for t in turns)
    return {
        "avg_words": words / max(len(turns), 1),
        "questions": sum(count_questions(t.text, cfg) for t in turns),
        "pushback": len(_hits(said, _patterns(cfg["difficulty"]["pushback"]))),
        "hedges": len(_hits(said, _patterns(cfg["hedges"]))),
    }


def _difficulty(stats: dict, objections: list[dict], cfg: dict) -> tuple[str, list[str]]:
    rules = cfg["difficulty"]
    points = len(objections) + stats["pushback"]
    why = [f"{len(objections)} objection(s)", f"{int(stats['pushback'])} push-back(s)"]
    if stats["avg_words"] <= rules["short_reply_words"]:
        points += rules["short_reply_points"]
        why.append(f"short replies ({stats['avg_words']:.0f} words on average)")
    level = "easy" if points <= rules["easy_max"] else "medium" if points <= rules["medium_max"] else "hard"
    return level, why


def _personality(stats: dict, cfg: dict) -> str:
    rules = cfg["personality"]
    traits = [
        t["text"] for t in rules["traits"]
        if ("at_least" not in t or stats[t["stat"]] >= t["at_least"])
        and ("at_most" not in t or stats[t["stat"]] <= t["at_most"])
    ]
    if not traits:
        return rules["default"]
    text = ", ".join(traits[:-1]) + (" and " if len(traits) > 1 else "") + traits[-1]
    return text[0].upper() + text[1:]


def build_profile(turns: list[Turn], roles: Roles, cfg: dict) -> Profile:
    """The prospect's profile from their turns in the call."""
    theirs = [t for t in turns if t.speaker == roles.prospect]
    said = [s for t in theirs for s in sentences(t.text)]
    cap = cfg["limits"]["max_list_items"]

    def quote(items: list[str]) -> list[str]:
        return [_quote(s, cfg) for s in items[:cap]]

    background = _hits(said, _patterns(cfg["background"]))
    needs = _hits(said, _patterns(cfg["needs"]))
    pains = _hits(said, _patterns(cfg["pains"]))
    money = re.compile(cfg["money"], re.IGNORECASE)
    spending = _patterns(cfg["budget_words"])
    budget = [s for s in said if money.search(s) and any(p.search(s) for p in spending)]
    objections = _objections(said, cfg)
    stats = _stats(theirs, said, cfg)
    difficulty, why = _difficulty(stats, objections, cfg)

    return Profile(
        name=display_name(roles.prospect, cfg),
        background=_quote(background[0], cfg) if background else "",
        personality=_personality(stats, cfg),
        budget=_quote(budget[0], cfg) if budget else "",
        needs=quote(needs),
        pain_points=quote(pains),
        objections=objections,
        difficulty=difficulty,
        evidence={
            "background": quote(background[1:]),
            "budget": [money.search(s).group(0) for s in budget[:cap]],
            "difficulty": why,
            "personality": [f"{stats['avg_words']:.0f} words per reply", f"{int(stats['questions'])} question(s) asked",
                            f"{int(stats['hedges'])} hedge(s)"],
        },
    )
