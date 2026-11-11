"""Transcript text -> speaker turns.

One parser per export layout, tried in `PARSERS` order; the first that finds a conversation wins. A parser takes
the cleaned lines and returns turns, or None when the text is not in its layout. To read a new export format,
write one parser and add it to `PARSERS`: nothing else changes.

Every parser returns turns in call order, with the speaker's consecutive lines already joined into one turn.
Speaker labels are matched only on short lines with single spaces (`clean_lines`), which keeps every pattern
here linear in the line length.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from core.infra.constants import CALL_LIMITS

# 5, 0:05, 00:05, 1:02:03, with optional .120 / ,120 fraction
_TS = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
_CUE_TIME = re.compile(rf"^({_TS})\s*-->\s*{_TS}")
_VOICE = re.compile(r"<v(?:\.[\w.-]+)?\s+([^>]+)>", re.IGNORECASE)
_TAG = re.compile(r"</?[^>]+>")
# A speaker label: a letter, then letters, digits, single spaces and . ' ’ - , ( ) / & (any script):
# "Norio Kobota (Sony Group)", "Mauch, Lukas", "Sarah Hakim (She/Her)". Bounded, so matching stays cheap.
_NAME = r"[^\W\d_](?:[\w.'’\-,()/&]| (?! )){0,60}?"
_AFFILIATION = re.compile(r"\s*\([^)]*\)")   # "(Sony Group)", "(She/Her)": dropped from the speaker's name
_LAST_FIRST = re.compile(r"^([^\W\d_][\w'’\-]*), ([^\W\d_][\w'’\-]*(?: [^\W\d_][\w'’\-]*)?)$")   # Teams: "Mauch, Lukas"
_BARE_TIME = re.compile(rf"^[\[(]?({_TS})[\])]?$")
# "[00:05] Name: text", "00:05 Name: text", "Name (00:05): text", "Name: text"
_LINE = re.compile(rf"^(?:[\[(]?({_TS})[\])]? ?[-–|]? ?)?({_NAME}) ?(?:[\[(]({_TS})[\])])? ?: (.+)$")
# A header line: a speaker and a time, nothing said, always with a gap (2+ spaces, kept as a tab by clean_lines),
# a separator or brackets between them, so speech that starts or ends with a time ("2:30 tomorrow.", "wake up at
# 7:00") is never a header. Name first: "Name  0:05" (Otter, Teams), "Name (00:00:05)", "[Name] 12:56:48" (Zoom
# saved), "Name | 0:05". Time first: "0:05 - Name" (Fathom), "0:00 | Name" (Gong), "[00:05] Name".
_HEADER_NAME_FIRST = re.compile(rf"^(?:\[({_NAME})\] ?|({_NAME})(?:\t| ?[-–|] ?| (?=[\[(])))[\[(]?({_TS})[\])]?$")
_HEADER_TIME_FIRST = re.compile(rf"^(?:({_TS}) [-–|] |\[({_TS})\] )({_NAME})$")


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
    """One entry per line: BOM, Windows endings and Markdown bold gone, tool junk removed, and spaces collapsed:
    a run of two or more becomes one tab (the gap some tools put between a speaker and a time), one stays one.

    Lines that are only junk become blank (`noise`); a junk prefix before real speech is cut off and the speech
    kept (`noise_prefixes`, e.g. Fathom's "BOOKMARK: ... - WATCH: <url>  what was said").
    """
    drop = [re.compile(p, re.IGNORECASE) for p in cfg["noise"]]
    cut = [re.compile(p, re.IGNORECASE) for p in cfg["noise_prefixes"]]
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").replace("**", "")
    lines = []
    for raw in text.split("\n"):
        line = re.sub("[ \u00a0]", " ", raw).strip()   # a non-breaking space is a space
        line = re.sub(r"[ \t]{2,}|\t", "\t", line)
        for prefix in cut:
            line = prefix.sub("", line).strip()
        lines.append("" if any(p.search(line) for p in drop) else line)
    return lines


def seconds(at: str | None) -> float:
    """"1:02:03.5" -> 3723.5; None -> 0 (a turn with no time keeps its place when sorting)."""
    if not at:
        return 0.0
    total = 0.0
    for part in at.replace(",", ".").split(":"):
        total = total * 60 + float(part)
    return total


def _speaker(name: str) -> str | None:
    """The label as a speaker name ("Last, First" turned round, affiliations dropped), or None when it is too long
    to be one: a sentence with a colon in it."""
    name = re.sub(r"\s+", " ", _AFFILIATION.sub("", html.unescape(name))).strip(" -–|,")
    name = _LAST_FIRST.sub(r"\2 \1", name)
    if not name or len(name) > CALL_LIMITS["max_speaker_chars"] or len(name.split()) > CALL_LIMITS["max_speaker_words"]:
        return None
    return name


def _header(line: str) -> tuple[str, str] | None:
    """(speaker, time) when the line is a speaker header; only short lines are tried."""
    if len(line) > CALL_LIMITS["max_header_chars"]:
        return None
    if m := _HEADER_NAME_FIRST.match(line):
        who, at = m.group(1) or m.group(2), m.group(3)
    elif m := _HEADER_TIME_FIRST.match(line):
        who, at = m.group(3), m.group(1) or m.group(2)
    else:
        return None
    who = _speaker(who)
    return (who, at) if who else None


def _labelled(line: str) -> tuple[str, str, str | None] | None:
    """(speaker, words, time) for a "Name: words" line. The label part must be short, so a long sentence with a
    colon late in it is never tried as one."""
    colon = line.find(": ")
    if colon < 0 or colon > CALL_LIMITS["max_header_chars"]:
        return None
    m = _LINE.match(line)
    who = _speaker(m.group(2)) if m else None
    return (who, m.group(4), m.group(1) or m.group(3)) if who else None


def _merge(turns: list[Turn]) -> list[Turn]:
    """One turn per stretch of one speaker: consecutive lines and cues by the same person are joined."""
    merged: list[Turn] = []
    for turn in turns:
        text = re.sub(r"\s+", " ", turn.text).strip()   # tabs from clean_lines back to plain spaces
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
    continues the last speaker. Cue ids and NOTE blocks have no time line, so they are never read as words.
    """
    turns: list[Turn] = []
    at, words = None, []

    def close():
        if at is None or not words:
            return
        text = " ".join(words)
        voice = _VOICE.search(text)
        who = _speaker(voice.group(1)) if voice else None
        body = html.unescape(_TAG.sub("", text)).strip()
        if not who and (prefixed := _labelled(body)):
            who, body, _ = prefixed
        if who or turns:
            turns.append(Turn(who or turns[-1].speaker, body, at))

    for line in lines:
        timed = _CUE_TIME.match(line)
        if timed or not line:
            close()
            at, words = (timed.group(1) if timed else None), []
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
    """A header line with the speaker and a time, then what they said on the lines below (Fathom, Otter, Gong,
    Zoom saved transcripts, Teams documents)."""
    turns, speaker, at, words, headers = [], None, None, [], 0
    for line in lines:
        if head := _header(line):
            if speaker and words:
                turns.append(Turn(speaker, " ".join(words), at))
            (speaker, at), words = head, []
            headers += 1
        elif line and speaker:
            words.append(line)
    if speaker and words:
        turns.append(Turn(speaker, " ".join(words), at))
    return _merge(turns) if headers >= 2 else None


def _lines(lines: list[str], cfg: dict) -> list[Turn] | None:
    """One "Name: words" per line (Google Meet, plain notes, Markdown "**Name:** words"), with an optional time
    before or after the name or on a line of its own; a line without a name continues the last speaker.

    A label used once ("Tip: ...", "Next step: ...", a Gemini note heading) is a heading, not a speaker: real
    speakers come back. Its line counts as plain text. Most lines must carry a recurring label, so prose with
    colons in it is not read as a conversation.
    """
    read = [(line, _labelled(line)) for line in lines if line and not _BARE_TIME.match(line)]
    uses = Counter(label[0] for _, label in read if label)
    recurring = {name for name, n in uses.items() if n >= 2}
    if not recurring:
        return None
    turns, named, clock = [], 0, None
    for line in lines:
        if not line:
            continue
        if bare := _BARE_TIME.match(line):   # Google Meet marks the time on a line of its own every minute or so
            clock = bare.group(1)
            continue
        label = _labelled(line)
        if label and label[0] in recurring:
            named += 1
            turns.append(Turn(label[0], label[1], label[2] or clock))
        elif turns:
            last = turns[-1]
            turns[-1] = Turn(last.speaker, f"{last.text} {line}", last.at)
    return _merge(turns) if named / len(read) >= 0.5 else None


# Tried in this order: the strictest layouts first, so a looser one never claims a stricter one's text.
PARSERS: tuple[tuple[str, Parser], ...] = (
    ("vtt", _vtt),
    ("srt", _srt),
    ("speaker_blocks", _blocks),
    ("speaker_lines", _lines),
)


def parse(text: str, cfg: dict) -> tuple[str, list[Turn]] | None:
    """(format name, turns) from the first parser that finds two or more speakers. Failing that, the first that
    found any turns (one speaker: the reader says so), else None."""
    lines = clean_lines(text, cfg)
    # A caption file (VTT / SRT timing lines) is only ever read as captions: its words are not speaker labels.
    captions = any(_CUE_TIME.match(line) for line in lines)
    single = None
    for name, parser in PARSERS[:2] if captions else PARSERS:
        turns = parser(lines, cfg)
        if not turns:
            continue
        if len({t.speaker for t in turns}) >= CALL_LIMITS["min_speakers"]:
            return name, turns
        single = single or (name, turns)
    return single
