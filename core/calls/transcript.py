"""Transcript text -> speaker turns.

One parser per export layout, tried in `PARSERS` order; the first that finds a conversation wins. A parser takes
the cleaned lines and returns turns, or None when the text is not in its layout. To read a new export format,
write one parser and add it to `PARSERS`: nothing else changes.

Every parser returns turns in call order, with the speaker's consecutive lines already joined into one turn.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

# 5, 0:05, 00:05, 1:02:03, with optional .120 / ,120 fraction
_TS = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
_CUE_TIME = re.compile(rf"^({_TS})\s*-->\s*{_TS}")
_VOICE = re.compile(r"<v(?:\.[\w.-]+)?\s+([^>]+)>", re.IGNORECASE)
_TAG = re.compile(r"</?[^>]+>")
# A speaker label: starts with a letter, then letters, digits, spaces and . ' ’ - , ( ) / & (any script):
# "Norio Kobota (Sony Group)", "Mauch, Lukas", "Sarah Hakim (She/Her)". Length is checked apart.
_NAME = r"[^\W\d_][\w.'’\-,()/& ]*?"
_AFFILIATION = re.compile(r"\s*\([^)]*\)")   # "(Sony Group)", "(She/Her)": dropped from the speaker's name
_BARE_TIME = re.compile(rf"^[\[(]?({_TS})[\])]?$")
# "[00:05] Name: text", "00:05 Name: text", "Name (00:05): text", "Name: text"
_LINE = re.compile(rf"^(?:[\[(]?({_TS})[\])]?\s*[-–|]?\s*)?({_NAME})\s*(?:[\[(]({_TS})[\])])?\s*:\s+(.+)$")
# A header line with a time and nothing said: "Name  0:05" (Otter, Teams), "Name (00:00:05)", "[Name] 12:56:48"
# (Zoom), "0:05 - Name" (Fathom), "0:00 | Name" (Gong), "[00:05] Name"
_HEADER_NAME_FIRST = re.compile(rf"^\[?({_NAME})\]?\s*[-–|]?\s*[\[(]?({_TS})[\])]?$")
_HEADER_TIME_FIRST = re.compile(rf"^[\[(]?({_TS})[\])]?\s*[-–|]?\s*({_NAME})$")


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    at: str | None = None   # when the turn starts, as written in the transcript


Parser = Callable[[list[str], dict], "list[Turn] | None"]


def sentences(text: str) -> list[str]:
    """The sentences of one turn, cut after . ! ? (every module that reads what was said uses this)."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def clean_lines(text: str, cfg: dict) -> list[str]:
    """Lines with BOM, Windows endings, edge spaces and known header/footer noise removed (blank lines kept)."""
    noise = [re.compile(p, re.IGNORECASE) for p in cfg["noise"]]
    lines = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").replace("**", "").split("\n")
    return ["" if any(n.search(line.strip()) for n in noise) else line.strip() for line in lines]


def seconds(at: str | None) -> float:
    """"1:02:03.5" -> 3723.5; None -> 0 (a turn with no time keeps its place when sorting)."""
    if not at:
        return 0.0
    total = 0.0
    for part in at.replace(",", ".").split(":"):
        total = total * 60 + float(part)
    return total


def _speaker(name: str, cfg: dict) -> str | None:
    """The label as a speaker name, or None when it is too long to be one (a sentence with a colon)."""
    name = re.sub(r"\s+", " ", _AFFILIATION.sub("", html.unescape(name))).strip(" -–|,")
    limit = cfg["limits"]["max_speaker_chars"]
    return name if name and len(name) <= limit and len(name.split()) <= 4 else None


def _merge(turns: list[Turn]) -> list[Turn]:
    """One turn per stretch of one speaker: consecutive lines and cues by the same person are joined."""
    merged: list[Turn] = []
    for turn in turns:
        text = re.sub(r"\s+", " ", turn.text).strip()
        if not text:
            continue
        if merged and merged[-1].speaker == turn.speaker:
            last = merged[-1]
            merged[-1] = Turn(last.speaker, f"{last.text} {text}", last.at)
        else:
            merged.append(Turn(turn.speaker, text, turn.at))
    return merged


def _cues(lines: list[str], cfg: dict) -> list[Turn] | None:
    """WebVTT / SRT: blocks of an optional id, a "start --> end" line and the words.

    The speaker is a <v Name> voice tag (Teams, Zoom) or a "Name: " prefix on the words; a cue with neither
    continues the last speaker.
    """
    turns, speaker, at, words = [], None, None, []

    def close():
        nonlocal words
        if at is not None and words:
            text = " ".join(words)
            voice = _VOICE.search(text)
            who = _speaker(voice.group(1), cfg) if voice else None
            body = html.unescape(_TAG.sub("", text)).strip()
            if not who:
                prefixed = _LINE.match(body)
                who = _speaker(prefixed.group(2), cfg) if prefixed else None
                body = prefixed.group(4) if prefixed and who else body
            if who or speaker:
                turns.append(Turn(who or speaker, body, at))
        words = []
        return (turns[-1].speaker if turns else speaker)

    for line in lines:
        timed = _CUE_TIME.match(line)
        if timed:
            speaker = close()
            at = timed.group(1)
        elif not line:
            speaker = close()
            at = None
        elif at is not None:
            words.append(line)
    close()
    # Teams writes overlapping cues out of order: put them back in time order (stable for equal times).
    return _merge(sorted(turns, key=lambda t: seconds(t.at))) or None


def _vtt(lines: list[str], cfg: dict) -> list[Turn] | None:
    return _cues(lines, cfg) if any(_CUE_TIME.match(line) and "." in line.split("-->")[0] for line in lines) else None


def _srt(lines: list[str], cfg: dict) -> list[Turn] | None:
    return _cues(lines, cfg) if any(_CUE_TIME.match(line) for line in lines) else None


def _blocks(lines: list[str], cfg: dict) -> list[Turn] | None:
    """A header line with the speaker and a time, then what they said on the lines below (Fathom, Otter,
    Teams/Meet documents): "Jane Smith  0:05" / "0:05 - Jane Smith" / "[00:05] Jane Smith"."""
    turns, speaker, at, words, headers = [], None, None, [], 0
    for line in lines:
        head = _HEADER_NAME_FIRST.match(line) or _HEADER_TIME_FIRST.match(line)
        if head:
            name_first = head.re is _HEADER_NAME_FIRST
            who = _speaker(head.group(1 if name_first else 2), cfg)
            if who:
                if speaker and words:
                    turns.append(Turn(speaker, " ".join(words), at))
                speaker, at, words = who, head.group(2 if name_first else 1), []
                headers += 1
                continue
        if line and speaker:
            words.append(line)
    if speaker and words:
        turns.append(Turn(speaker, " ".join(words), at))
    return _merge(turns) if headers >= 2 else None


def _lines(lines: list[str], cfg: dict) -> list[Turn] | None:
    """One "Name: words" per line (Google Meet, plain notes, Markdown "**Name:** words"), with an optional time
    before or after the name or on a line of its own; a line without a name continues the last speaker. Most lines must carry a name, so prose with a colon in it is not read as this."""
    turns, said, named, clock = [], 0, 0, None
    for line in lines:
        if not line:
            continue
        bare = _BARE_TIME.match(line)
        if bare:   # Google Meet marks the time on a line of its own every minute or so
            clock = bare.group(1)
            continue
        said += 1
        match = _LINE.match(line)
        who = _speaker(match.group(2), cfg) if match else None
        if who:
            named += 1
            turns.append(Turn(who, match.group(4), match.group(1) or match.group(3) or clock))
        elif turns:
            last = turns[-1]
            turns[-1] = Turn(last.speaker, f"{last.text} {line}", last.at)
    # A label used once ("The plan: ship Friday") is a heading, not a speaker: real speakers come back.
    lines_per_name = Counter(t.speaker for t in turns)
    recurring = sum(1 for n in lines_per_name.values() if n >= 2)
    return _merge(turns) if said and named / said >= 0.5 and recurring >= cfg["limits"]["min_speakers"] else None


# Tried in this order: the strictest layouts first, so a looser one never claims a stricter one's text.
PARSERS: tuple[tuple[str, Parser], ...] = (
    ("vtt", _vtt),
    ("srt", _srt),
    ("speaker_blocks", _blocks),
    ("speaker_lines", _lines),
)


def parse(text: str, cfg: dict) -> tuple[str, list[Turn]] | None:
    """(format name, turns) from the first parser that finds two or more speakers, else None."""
    lines = clean_lines(text, cfg)
    for name, parser in PARSERS:
        turns = parser(lines, cfg)
        if turns and len({t.speaker for t in turns}) >= cfg["limits"]["min_speakers"]:
            return name, turns
    return None
