"""Tone marks in script lines: how a line is meant to sound, drawn by the chat screen and the voice.

    **word**   loud stress: drawn in bold
    _word_     stretched stress: drawn in italics
    ==words==  the key thing: drawn with a soft highlight
    ...  …     a short pause: kept as it is (the voice pauses on it)
    ¶ [pause]  a long pause: what follows is a new chat bubble, after typing dots
    (slow)     a tone note in front of a line: never shown or said; the voice reads it (see web lib/tone.ts)

The marks travel with the line to the screen. Anything that reads the line as words (an AI prompt, a
check) takes `plain(line)`."""

import re

PAUSE = "¶"
KEY = re.compile(r"==(.+?)==")
LOUD = re.compile(r"\*\*(\S(?:.*?\S)?)\*\*")
LONG_PAUSE = re.compile(r"\s*\[pause[^\]]*\]\s*")
TONES = ("slow", "deliberate", "calm", "gentle", "soft", "warm", "serious", "firm", "curious", "playful", "excited", "upbeat")
NOTE = re.compile(rf"\((?:{'|'.join(TONES)})(?:,\s*(?:{'|'.join(TONES)}))*\)\s*")
STRESS = re.compile(r"(^|[\s(\"'“‘])_(\w[^_]*?)_(?=[\s.,!?…:;)—\-\"'”’]|$)")  # "_all_", never belief_cost


def plain(text):
    """The words without their marks; a pause reads as a space."""
    text = NOTE.sub("", LOUD.sub(r"\1", KEY.sub(r"\1", text or "")))
    text = LONG_PAUSE.sub(f" {PAUSE} ", text)
    text = STRESS.sub(r"\1\2", text)
    return re.sub(rf"\s*{PAUSE}\s*", " ", text).strip()


def stresses(line):
    """How many words the line stresses (any mark)."""
    line = line or ""
    return len(KEY.findall(line)) + len(STRESS.findall(line)) + len(LOUD.findall(line))


def join(first, then):
    """Two lines said one after the other, each in its own bubble."""
    parts = (p.strip().strip(PAUSE).strip() for p in (first, then) if p)
    return PAUSE.join(p for p in parts if p)
