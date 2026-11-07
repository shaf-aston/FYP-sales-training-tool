"""One reply, read once: cut into parts, each part tagged with what it does. Every other hearing rule reads
these parts, so a reply is never cut two ways ("i guess 3 years, what about you?": a hedge, an answer and a
question, not one question that loses the answer).

  hedge  "idk", "honestly no idea": says nothing on its own, never what they meant
  tag    "you know?", "right?": talk, not a question
  asks   "what about you?", "how much is it", "is this legit": a question
  rise   ends in "?" but isn't phrased as a question ("a year?", "what's this going to cost me?"): the Ear
         settles it per step (`Reply.settle`), as content said with a rise or as a question
  said   everything else: the content

A self-correction (`take_backs`: "3 years, sorry, 2 years") takes back what came before it; only the rest is read.
"""

import re
from dataclasses import dataclass, replace

from core.infra.utils import opens_question, tokenize


@dataclass(frozen=True)
class Part:
    text: str
    act: str   # said | asks | rise | hedge | tag


@dataclass(frozen=True)
class Reply:
    text: str          # as typed
    unnudged: str      # without a nudge on its end ("credit, what's next?" -> "credit") or what a correction took back; "" when only a nudge
    nudged: bool       # a nudge was cut off its end
    parts: tuple

    def settle(self, said):
        """Each `rise` part made content when `said(part)` holds, else a question."""
        return replace(self, parts=tuple(Part(p.text, ("said" if said(p.text) else "asks") if p.act == "rise" else p.act)
                                         for p in self.parts))

    def _joined(self, acts):
        kept = [p for p in self.parts if p.act in acts]
        if len(kept) == len(self.parts):
            return self.unnudged  # nothing left out: the reply as typed, never re-punctuated
        return ", ".join(p.text.rstrip("?").strip() if p.act == "said" else p.text for p in kept)

    @property
    def said(self):
        """The content: what answers the step ("3 years"), hedges, tags and questions left out."""
        return self._joined({"said"}) if any(p.act == "said" for p in self.parts) else ""

    @property
    def asked(self):
        """The question parts ("what about you?"); "" when nothing is asked."""
        return self._joined({"asks"}) if any(p.act == "asks" for p in self.parts) else ""

    @property
    def meant(self):
        """Content and questions, hedges and tags left out: "I don't know, is this legit?" -> "is this legit?"."""
        return self._joined({"said", "asks"}) if any(p.act in ("said", "asks") for p in self.parts) else self.unnudged


def break_pattern(cfg):
    """The one place a reply is cut: at `clause_breaks` (punctuation only before a space or the end, so "2.5k"
    stays whole; words as whole words)."""
    parts = [rf"\b{re.escape(b)}\b" if b.isalpha() else rf"{re.escape(b)}(?=\s|$)" for b in cfg["clause_breaks"]]
    return re.compile("|".join(parts), re.IGNORECASE)


def clauses(text, breaks):
    """The reply's parts, in order; a "?" stays on the part it ends ("dunno, a year?" -> "dunno", "a year?")."""
    parts, start = [], 0
    for found in breaks.finditer(text):
        parts.append(text[start:found.end() if found.group() == "?" else found.start()])
        start = found.end()
    parts.append(text[start:])
    return [p.strip(" \t,;.!") for p in parts if tokenize(p)]


def after_lead(text, breaks):
    """What follows the reply's first part ("make money online so I can quit my job" -> "I can quit my job"),
    "" when it has one part only."""
    found = breaks.search(text)
    rest = text[found.end():].strip(" \t,;.!") if found else ""
    return rest if tokenize(rest) else ""


class Reader:
    def __init__(self, cfg, nudges, hedges):
        """`nudges`: phrases cut off the end of a reply. `hedges(text)`: the part says nothing on its own."""
        self.cfg, self.breaks, self._hedges = cfg, break_pattern(cfg), hedges
        leads = "|".join(map(re.escape, cfg["nudge_leads"]))
        self._nudges = [re.compile(rf"(?:^|\W)(?:(?:{leads})\W+)?{words}\W*$", re.IGNORECASE)
                        for words in (r"\W+".join(map(re.escape, tokenize(p))) for p in sorted(nudges, key=len, reverse=True))]
        self._tags = {" ".join(tokenize(t)) for t in cfg["filler_tags"]}
        self._starts = set(cfg["question_words"]) | set(cfg["closed_question_starts"])
        backs = [r"\W+".join(map(re.escape, tokenize(b))) for b in sorted(cfg["take_backs"], key=len, reverse=True)]
        words = "|".join(b for b in backs if "\\W+" in b)   # "no actually my credit card"
        word = "|".join(b for b in backs if "\\W+" not in b)  # one word needs a break after it: "sorry my dog is barking" isn't one
        # at the start or after a break, with words after it: "nothing, sorry" takes nothing back
        self._take_back = re.compile(rf"(?:^|[,;.!?]\s*)(?:(?:{words})\b[\s,;.!-]*|(?:{word})\s*[,;.!-][\s,;.!-]*)(?=\w)",
                                     re.IGNORECASE)

    def read(self, text):
        rest, nudged = text, False
        for nudge in self._nudges:
            found = nudge.search(text)
            if found:
                rest, nudged = text[:found.start()].rstrip(" ,;:-"), True
                break
        while back := self._take_back.search(rest):  # "3k, no wait, more like 4k" -> "more like 4k": they took
            rest = rest[back.end():]  # the first part back; cut again so "wait, sorry, what's the price?" asks
        parts, acts = clauses(rest, self.breaks), []
        for part in parts:
            act = self._act(part, len(parts) > 1)
            acts.append("said" if act == "rise" and acts[-1:] == ["hedge"] else act)  # "lol idk, money?": unsure, not asking
        return Reply(text, rest, nudged, tuple(map(Part, parts, acts)))

    def asks(self, part):
        """Phrased as a question: it opens like one ("is this legit", "how much is it"), or it ends in "?" and
        starts with a question word or a helper verb ("what?", "is it?")."""
        words = tokenize(part)
        first = words[0] if words else ""
        said_as = {first, first.split("'")[0], first.removesuffix("s")}  # "what's", "whats" -> what
        return opens_question(part, self.cfg) or (part.rstrip().endswith("?") and bool(said_as & self._starts))

    def _act(self, part, several):
        if " ".join(tokenize(part)) in self._tags:
            return "tag"
        if self.asks(part):
            return "asks"
        if part.rstrip().endswith("?"):
            return "rise"
        if several and self._hedges(part):  # a reply that is only a hedge is a shrug: heard whole (shrug.py)
            return "hedge"
        return "said"
