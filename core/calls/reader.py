"""The one door into core/calls: read a transcript into speakers, roles, turns and the prospect's profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from core.calls.errors import (
    CALL_ONE_SPEAKER,
    CALL_TOO_LONG,
    CALL_TOO_SHORT,
    CALL_UNREADABLE,
    CallError,
)
from core.calls.profile import Profile, build_profile
from core.calls.roles import Roles, SpeakerStats, assign_roles, speaker_stats
from core.calls.transcript import Turn, parse
from core.infra.constants import CALL_LIMITS
from core.infra.loader import load_yaml


def load_calls_config() -> dict:
    return load_yaml("calls.yaml")


@dataclass(frozen=True)
class CallReading:
    format: str
    speakers: list[SpeakerStats]
    roles: Roles
    turns: list[Turn]
    profile: Profile

    def history(self) -> list[dict]:
        """The call as a sell-mode transcript: the rep is the "user" (the learner), the prospect the
        "assistant" (the buyer). Anyone else's turns are left out; they are neither side of the sale."""
        side = {self.roles.rep: "user", self.roles.prospect: "assistant"}
        history: list[dict] = []
        for turn in self.turns:
            role = side.get(turn.speaker)
            if role is None:
                continue
            if history and history[-1]["role"] == role:   # someone else spoke between: one side, one turn
                history[-1] = {"role": role, "content": f"{history[-1]['content']} {turn.text}"}
            else:
                history.append({"role": role, "content": turn.text})
        return history

    def to_json(self) -> dict:
        return {
            "format": self.format,
            "speakers": [asdict(s) for s in self.speakers],
            "rep": {"name": self.roles.rep, "how": self.roles.how, "sure": self.roles.sure},
            "prospect": self.roles.prospect,
            "turns": [{**asdict(t), "role": self.roles.role_of(t.speaker)} for t in self.turns],
            "profile": asdict(self.profile),
        }


def read_call(text: str, rep: str | None = None, cfg: dict | None = None) -> CallReading:
    """Read a transcript. `rep` is the learner's speaker name when they told us; else it is guessed.

    Raises CallError: CALL_TOO_LONG, CALL_UNREADABLE, CALL_ONE_SPEAKER, CALL_TOO_SHORT or UNKNOWN_SPEAKER.
    """
    cfg = cfg or load_calls_config()
    if len(text) > CALL_LIMITS["max_chars"]:
        raise CallError(CALL_TOO_LONG, f"{len(text)} characters")
    parsed = parse(text, cfg)
    if parsed is None:
        raise CallError(CALL_UNREADABLE)
    fmt, turns = parsed
    stats = speaker_stats(turns, cfg)
    if len(stats) < CALL_LIMITS["min_speakers"]:
        raise CallError(CALL_ONE_SPEAKER, stats[0].name)
    if len(turns) < CALL_LIMITS["min_turns"]:
        raise CallError(CALL_TOO_SHORT, f"{len(turns)} turns")
    roles = assign_roles(stats, cfg, named=rep)
    return CallReading(fmt, stats, roles, turns, build_profile(turns, roles, cfg))
