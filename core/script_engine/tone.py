"""Tone marks in script lines: how a line is meant to sound, drawn by the chat screen and the voice.

    _word_     stress: drawn in italics
    ==words==  the key thing: drawn with a soft highlight
    ¶          a pause: what follows is a new chat bubble, after typing dots

The marks travel with the line to the screen. Anything that reads the line as words (an AI prompt, a
check) takes `plain(line)`."""

import re

PAUSE = "¶"
KEY = re.compile(r"==(.+?)==")
STRESS = re.compile(r"(^|[\s(\"'])_(\w[^_]*?)_(?=[\s.,!?…\"']|$)")  # "_all_", never belief_cost


def plain(text):
    """The words without their marks; a pause reads as a space."""
    text = KEY.sub(r"\1", text or "")
    text = STRESS.sub(r"\1\2", text)
    return re.sub(r"\s*¶\s*", " ", text).strip()


def stresses(line):
    """How many words the line stresses (either mark)."""
    return len(KEY.findall(line or "")) + len(STRESS.findall(line or ""))


def join(*parts):
    """Lines said one after the other, each in its own bubble."""
    return PAUSE.join(p.strip() for p in parts if p and p.strip())
