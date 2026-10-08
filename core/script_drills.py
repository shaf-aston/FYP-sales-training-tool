"""Recall practice: lines with the load-bearing part blanked out.

Recognising a good line is easy; producing one under pressure is the skill being
trained. So a drill shows the line with the move removed, the learner produces it
in their head, and only then reveals it.

Two sources feed the same drill shape: lines authored in config/script_drills.yaml,
and the learner's own strongest turns from a session they just played.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import load_yaml
from .selling_quality import load_selling_signals

BLANK_PATTERN = re.compile(r"\[([^\[\]]+)\]")
OWN_LINE_GROUP = "your_own_lines"


@dataclass(frozen=True)
class Drill:
    """One line to recall, split into the visible parts and the hidden ones."""

    id: str
    group: str
    label: str
    segments: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    source: str = "authored"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "group": self.group,
            "label": self.label,
            "segments": list(self.segments),
            "answers": list(self.answers),
            "source": self.source,
        }


def split_blanks(line: str) -> tuple[list[str], list[str]]:
    """Split "Before I [ask] this" into the visible text and the hidden answers.

    Returns (segments, answers) where segments has exactly one more entry than
    answers, so the two interleave: segment, blank, segment, blank, segment.
    """
    segments, answers, cursor = [], [], 0
    for match in BLANK_PATTERN.finditer(line):
        segments.append(line[cursor:match.start()])
        answers.append(match.group(1).strip())
        cursor = match.end()
    segments.append(line[cursor:])
    return segments, answers


def load_drills() -> list[Drill]:
    """Every authored drill, in config order. Lines with no blank are skipped."""
    config = load_yaml("script_drills.yaml") or {}
    drills = []
    for group in config.get("groups", []):
        group_id = group.get("id", "")
        label = group.get("label", group_id)
        for index, line in enumerate(group.get("lines", [])):
            segments, answers = split_blanks(line)
            if not answers:
                continue
            drills.append(
                Drill(
                    id=f"{group_id}:{index}",
                    group=group_id,
                    label=label,
                    segments=segments,
                    answers=answers,
                )
            )
    return drills


def group_summaries() -> list[dict]:
    """Group id, name and why it matters, for the drill screen's headings."""
    config = load_yaml("script_drills.yaml") or {}
    return [
        {
            "id": group.get("id", ""),
            "label": group.get("label", group.get("id", "")),
            "why": (group.get("why") or "").strip(),
        }
        for group in config.get("groups", [])
    ]


def drills_from_own_turns(review_turns: list[dict], limit: int | None = None) -> list[Drill]:
    """Turn the learner's own strongest lines into drills.

    Revising something you actually said beats revising a stranger's script. The
    blank is the second half of the sentence, which is where the move usually
    lands, and the drill is skipped when there is no sensible place to split.
    """
    strong_rating = load_selling_signals()["thresholds"]["strong_rating"]
    limit = limit or _own_lines()["max_drills"]
    strong = [
        turn
        for turn in review_turns or []
        if turn.get("rating", 0) >= strong_rating and turn.get("seller")
    ]
    strong.sort(key=lambda turn: (-turn.get("rating", 0), turn.get("turn", 0)))

    # Walk the whole list, not the first `limit` of it: a line too short to split
    # would otherwise silently cost the learner a drill instead of being skipped
    # in favour of their next best line.
    drills = []
    for turn in strong:
        if len(drills) >= limit:
            break
        split = _split_point(turn["seller"])
        if split is None:
            continue
        visible, hidden = split
        drills.append(
            Drill(
                id=f"{OWN_LINE_GROUP}:{turn.get('turn', len(drills))}",
                group=OWN_LINE_GROUP,
                label="Lines you got right",
                segments=[visible, ""],
                answers=[hidden],
                source="own_turn",
            )
        )
    return drills


def _own_lines() -> dict:
    """The own-line drill limits from script_drills.yaml."""
    return load_yaml("script_drills.yaml")["own_lines"]


def _split_point(line: str) -> tuple[str, str] | None:
    """Split a sentence so the blank covers the move, not a stray word."""
    words = line.split()
    if len(words) < _own_lines()["min_words"]:
        return None
    cut = len(words) // 2
    return " ".join(words[:cut]) + " ", " ".join(words[cut:])


def build_drill_set(review_turns: list[dict] | None = None) -> dict:
    """The full drill set for the practice screen.

    The learner's own lines come first when a session supplied any, because they
    are the ones they are most likely to use again.
    """
    own = drills_from_own_turns(review_turns or [])
    groups = group_summaries()
    if own:
        groups = [
            {
                "id": OWN_LINE_GROUP,
                "label": "Lines you got right",
                "why": "Your own strongest turns from the session you just played.",
            }
        ] + groups
    return {
        "groups": groups,
        "drills": [drill.to_dict() for drill in own + load_drills()],
    }
