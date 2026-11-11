"""Who is who in a call: the rep (the learner) and the prospect they were selling to.

The learner can name the rep. Otherwise the rep is the speaker who asks the most questions (reps run calls by
asking), and it is "sure" only when that lead is clear; with no questions at all, the first speaker is the rep.
The prospect is whoever else talked the most.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.calls.errors import UNKNOWN_SPEAKER, CallError
from core.calls.transcript import Turn, sentences

NAMED, MOST_QUESTIONS, FIRST_SPEAKER = "named", "most_questions", "first_speaker"


@dataclass(frozen=True)
class SpeakerStats:
    name: str
    turns: int
    words: int
    questions: int


@dataclass(frozen=True)
class Roles:
    rep: str
    prospect: str
    how: str      # NAMED, MOST_QUESTIONS or FIRST_SPEAKER
    sure: bool    # False: the guess is close; the UI asks the learner to check it

    def role_of(self, speaker: str) -> str:
        return "rep" if speaker == self.rep else "prospect" if speaker == self.prospect else "other"


def count_questions(text: str, cfg: dict) -> int:
    """Sentences that ask: they end in "?", or open with a request that asks without one ("tell me about...").
    A sentence that only opens like a question ("When we started, ...", "What a mess.") does not count."""
    starts = tuple(f"{w} " for w in cfg["rep"]["ask_starts"])
    return sum(1 for s in sentences(text) if s.endswith("?") or s.lower().startswith(starts))


def speaker_stats(turns: list[Turn], cfg: dict) -> list[SpeakerStats]:
    """Per speaker, in order of first appearance."""
    order: dict[str, list[int]] = {}
    for turn in turns:
        counts = order.setdefault(turn.speaker, [0, 0, 0])
        counts[0] += 1
        counts[1] += len(turn.text.split())
        counts[2] += count_questions(turn.text, cfg)
    return [SpeakerStats(name, *counts) for name, counts in order.items()]


def _words(name: str) -> list[str]:
    """A name's words, lower case, in order: "Mauch, Lukas" and "Lukas Mauch" are the same name."""
    return sorted(re.findall(r"[^\W_]+", name.lower()))


def _match(named: str, speakers: list[str]) -> str | None:
    """The speaker the learner meant, punctuation and case aside: the same name, else the only speaker with that
    one word in their name ("Lukas" or "Mauch" for "Lukas Mauch")."""
    want = _words(named)
    if not want:
        return None
    same = [s for s in speakers if _words(s) == want]
    if same:
        return same[0]
    partial = [s for s in speakers if len(want) == 1 and want[0] in _words(s)]
    return partial[0] if len(partial) == 1 else None


def assign_roles(stats: list[SpeakerStats], cfg: dict, named: str | None = None) -> Roles:
    """Raises CallError(UNKNOWN_SPEAKER) when `named` speaks nowhere in the call."""
    names = [s.name for s in stats]
    if named:
        rep = _match(named, names)
        if rep is None:
            raise CallError(UNKNOWN_SPEAKER, named)
        how, sure = NAMED, True
    else:
        ranked = sorted(stats, key=lambda s: s.questions, reverse=True)
        top, runner = ranked[0], ranked[1]
        if top.questions == 0:
            rep, how, sure = names[0], FIRST_SPEAKER, False
        else:
            rep, how = top.name, MOST_QUESTIONS
            sure = top.questions >= cfg["rep"]["sure_ratio"] * max(runner.questions, 1)
    others = [s for s in stats if s.name != rep]
    prospect = max(others, key=lambda s: s.words).name
    return Roles(rep, prospect, how, sure)
