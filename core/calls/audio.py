"""A call recording -> a transcript the reader can read: "[m:ss] Speaker A: ..." lines.

The one part of core/calls that uses AI, and only through the functions it is given: `transcribe` (speech to
timed segments) and `ask` (one prompt in, one reply out). Speech engines do not tell voices apart, so the AI labels
each segment A or B from what is said, in batches that repeat the last few labelled segments for continuity.
The result is ordinary text: the learner sees it, can fix a label by editing it, then reads it like any transcript.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from core.infra.constants import TRANSCRIPTION
from core.infra.providers.transcribe import Segment

# "14. B", "14: B", "14) Speaker B", "**14.** B", "14 -> B", "14=B", "- 14. B"
_LABEL = re.compile(r"^[\s\-*>]*(\d+)\**\s*(?:[:.)=]|->|-)?\s*\**\s*(?:speaker\s*)?([AB])\b", re.IGNORECASE | re.MULTILINE)
SPEAKERS = ("A", "B")


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 3600}:{whole // 60 % 60:02d}:{whole % 60:02d}" if whole >= 3600 else f"{whole // 60}:{whole % 60:02d}"


def label_speakers(segments: list[Segment], ask: Callable[[str], str], prompt: str) -> tuple[list[str], bool]:
    """("A" or "B" per segment, sure). A segment the AI left out keeps the label before it (the same speaker going on);
    the first speaker is A. A batch with under half its labels readable is asked once more; `sure` is False when
    under half of all labels came back readable, so the learner is told to check them. `prompt` has {context} and
    {segments} blanks."""
    labels: list[str] = []
    readable = 0
    batch, context = TRANSCRIPTION["label_batch"], TRANSCRIPTION["label_context"]
    for start in range(0, len(segments), batch):
        shown = range(max(0, start - context), start)
        numbered = range(start, min(start + batch, len(segments)))
        question = prompt.format(
            context="\n".join(f"{i + 1}. {labels[i]}: {segments[i].text}" for i in shown) or "(none: this is the start)",
            segments="\n".join(f"{i + 1}. {segments[i].text}" for i in numbered),
        )
        said = _parse(ask(question), numbered)
        if len(said) < len(numbered) / 2:
            said = _parse(ask(question), numbered) or said
        readable += len(said)
        for i in numbered:
            labels.append(said.get(i) or (labels[-1] if labels else "A"))
    return labels, readable >= len(segments) / 2


def _parse(reply: str, numbered: range) -> dict[int, str]:
    """Segment index -> label, for the numbers this batch asked about."""
    return {int(n) - 1: who.upper() for n, who in _LABEL.findall(reply or "") if int(n) - 1 in numbered}


def as_transcript(segments: list[Segment], labels: list[str]) -> str:
    """One line per stretch of one speaker: "[0:05] Speaker A: what they said"."""
    lines: list[str] = []
    last = None
    for segment, who in zip(segments, labels):
        if who == last:
            lines[-1] += f" {segment.text}"
        else:
            lines.append(f"[{_clock(segment.start)}] Speaker {who}: {segment.text}")
            last = who
    return "\n".join(lines)
