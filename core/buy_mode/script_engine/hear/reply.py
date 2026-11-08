"""One reply, read once: cut into parts, each part tagged with what it does. Every other hearing rule reads
these parts, so a reply is never cut two ways ("i guess 3 years, what about you?": a hedge, an answer and a
question, not one question that loses the answer).

  hedge  "idk", "honestly no idea", "sorry for the long message" (`aside_starts`), "sorry" beside an answer
         (`no_answer_words`): says nothing on its own, never what they meant
  tag    "you know?", "right?": talk, not a question
  asks   "what about you?", "how much is it", "is this legit": a question
  rise   ends in "?" but isn't phrased as a question ("a year?", "what's this going to cost me?"): the Ear
         settles it per step (`Reply.settle`), as content said with a rise or as a question
  said   everything else: the content

A lead that asks leave to answer (`answer_leads`: "is it ok to say quit my job?") is cut off: the rest is the answer.
A self-correction (`take_backs`: "3 years, sorry, 2 years") takes back what came before it; only the rest is read.
A yes and no said together (`flip_leads`: "no yeah", "yeah no") mean the last one.
"""

import re
from dataclasses import dataclass, replace

from core.buy_mode.script_engine.config import plain_words
from core.infra.utils import opens_question, tokenize
from core.buy_mode.script_engine.words.fill import number_phrase, short_form


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
        if len(kept) == len(self.parts):  # nothing left out: the reply as typed, never re-punctuated
            if all(p.act == "said" for p in kept):  # round 48: "maybe money?" got "What do you mean by money?";
                return self.unnudged.rstrip(" ?")     # a "?" on what they said goes, as when parts are joined
            return self.unnudged
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
    stays whole, and a comma also before a letter: "more money,more time"; words as whole words)."""
    ends = {",": r"(?=\s|$|[^\W\d])"}
    parts = [rf"\b{re.escape(b)}\b" if b.isalpha() else re.escape(b) + ends.get(b, r"(?=\s|$)") for b in cfg["clause_breaks"]]
    return re.compile("|".join(parts), re.IGNORECASE)


def clauses(text, breaks):
    """The reply's parts, in order; a "?" stays on the part it ends ("dunno, a year?" -> "dunno", "a year?")."""
    parts, start = [], 0
    for found in breaks.finditer(text):
        parts.append(text[start:found.end() if found.group() == "?" else found.start()])
        start = found.end()
    parts.append(text[start:])
    return [p.strip(" \t,;.!") for p in parts if tokenize(p)]


def after(text, part):
    """What follows one of the reply's parts ("make money online" in "make money online so I can quit my job"
    -> "so I can quit my job"); "" when nothing does."""
    rest = text[text.find(part) + len(part):].strip(" \t,;.!") if part and part in text else ""
    return rest if tokenize(rest) else ""


class Reader:
    def __init__(self, cfg, nudges, hedges):
        """`nudges`: phrases cut off the end of a reply. `hedges(text)`: the part says nothing on its own."""
        self.cfg, self.breaks, self._hedges = cfg, break_pattern(cfg), hedges
        leads = "|".join(map(re.escape, cfg["nudge_leads"]))
        broken = set(cfg["nudge_after_break"])   # "what happens next?" keeps its "next"; "debit, next" does not
        self._nudges = [re.compile(rf"(?:^|{r'[^\w\s]' if p in broken else ''}\W)(?:(?:{leads})\W+)?{words}\W*$", re.IGNORECASE)
                        for p, words in ((p, r"\W+".join(map(re.escape, tokenize(p)))) for p in sorted(nudges, key=len, reverse=True))]
        self._tags = {" ".join(tokenize(t)) for t in [*cfg["filler_tags"], *cfg["end_tags"]]}
        self._tag_skip = frozenset(cfg["tag_skip"])  # "to be completely honest" is "to be honest"
        self._starts = set(cfg["question_words"]) | set(cfg["closed_question_starts"])
        def any_of(phrases):
            return "|".join(r"\W+".join(map(re.escape, tokenize(b))) for b in sorted(phrases, key=len, reverse=True))
        words = any_of(cfg["take_backs"])   # "no actually my credit card"
        word = any_of(cfg["take_backs_with_break"])  # needs a break after it: "sorry my dog is barking" isn't one
        mid = any_of(cfg["take_backs_mid"])
        not_mid = "".join(rf"(?<!\b{re.escape(b)})" for b in cfg["take_backs_mid"] if " " not in b)  # "no, no, I can't" is a no
        # at the start or after a break, with words after it: "nothing, sorry" takes nothing back; a mid one
        # ("no") only between two parts: "a year, no, two years" corrects, "no, credit?" says no
        self._blank = set(cfg["no_answer_words"])  # "yes, sorry": a part of only these beside others says nothing
        self._blank_end = re.compile(rf"(?<=\w)\s+((?:{any_of(cfg['no_answer_words'])})\W*)$", re.IGNORECASE)
        self._unsure_end = re.compile(rf"(?<=\w)\s+((?:{any_of(cfg['unsure_ends'])})\W*)$", re.IGNORECASE)
        self._plain = plain_words(cfg)
        self._tag_end = re.compile(rf"(?<=\w)\s+(?:{any_of(cfg['end_tags'])})\W*$", re.IGNORECASE)
        self._unsure = re.compile(rf"^\W*(?:{any_of(cfg['unsure_leads'])})\b", re.IGNORECASE)
        self._aside = re.compile(rf"^\W*(?:{any_of(cfg['aside_starts'])})\b", re.IGNORECASE)
        self._ask_lead = re.compile(rf"^\W*(?:{any_of(cfg['ask_leads'])})\b\W*", re.IGNORECASE)
        flips = "|".join(rf"{re.escape(a)}\W+(?={re.escape(b)}\s*(?:[,;.!?]|$))" for a, b in map(tokenize, cfg["flip_leads"]))
        self._flip = re.compile(rf"^\W*(?:{flips})", re.IGNORECASE)  # "no yeah" is a yes, "yeah no" a no: the last word counts
        self._filler_lead = re.compile(rf"^\W*(?:{any_of(cfg['filler_leads'])})\b\W*", re.IGNORECASE)
        self._answer_lead = re.compile(rf"^\W*(?:{any_of(cfg['answer_leads'])})\b\W*", re.IGNORECASE)
        self._take_back = re.compile(rf"(?:^|[,;.!?]\s*)(?:(?:{words})\b[\s,;.!-]*|(?:{word})\s*[,;.!-][\s,;.!-]*)(?=\w)"
                                     rf"|(?<=\w){not_mid}[,;.!?]\s*(?:{mid})\s*[,;.!-][\s,;.!-]*(?=\w)", re.IGNORECASE)

        # "2k, no 3k", "more time, sorry more money": between two answers of one kind a correction needs no break
        # after it (round 33/34 callers: the first was kept); "yes, sorry the baby was crying" is two kinds, so stays
        self._amount = re.compile(rf"\d\w*|(?:{any_of(cfg['number_words'])})", re.IGNORECASE)
        self._bare = re.compile(rf"\d+(?:[.,]\d+)?|(?:{any_of(cfg['number_words'])})", re.IGNORECASE)  # "2k" has its unit
        self._fix_back = re.compile(rf"(?<=\w){not_mid}[,;.!?]\s*(?:{mid}|{word})\s+(?=\w)", re.IGNORECASE)
        self._denied = re.compile(rf"^\W*(?:{any_of(cfg['denied_leads'])})\s+(?=\w)", re.IGNORECASE)  # "not a year, two"
        self._cfg = cfg

    def _figure(self, text):
        """A figure or span is in it: a digit, a number word that is no stop word, or a number with its unit."""
        words = tokenize(text)
        return any(w[0].isdigit() or (w in self._cfg["number_words"] and w not in self._cfg["stop_words"]) for w in words) or any(
            number_phrase(text, rule, self._cfg) for rule in self._cfg["number_blanks"].values())

    def _fixed_in(self, text):
        """A correction between two answers of one kind ("2k, no 3k", "more time, sorry more money", "not 2k,
        3k"): the words kept, else None."""
        back, denied = self._fix_back.search(text), self._denied.match(text)
        cut = clauses(text[denied.end():], self.breaks) if denied else []
        if not back and len(cut) < 2:
            return None
        taken = text[:back.start()] if back else cut[0]  # "not a year, two": the year is denied, two is kept
        before, new = tokenize(clauses(taken, self.breaks)[-1]), text[back.end():].strip() if back else after(text, cut[0])
        if not ((self._figure(" ".join(before)) and self._figure(new)) or before[:1] == tokenize(new)[:1]):
            return None
        return self._with_unit(taken, new)

    def _with_unit(self, taken, new):
        """The words kept after a correction. A bare amount keeps the unit said after the first one: "a year,
        well two" -> "two year" (round 50 callers: "a year, no, two" was a bare "two" and missed)."""
        last = clauses(taken, self.breaks)
        before = tokenize(last[-1]) if last else []
        said = [i for i, w in enumerate(before) if self._amount.fullmatch(w)]
        bare = said and all(self._bare.fullmatch(w) for w in tokenize(new))  # "a million, jk, 2k": 2k
        return " ".join([new, *before[said[-1] + 1:]]) if bare else new

    def read(self, text):
        rest, nudged = text, False
        for nudge in self._nudges:
            found = nudge.search(text)
            if found:
                rest, nudged = text[:found.start()].rstrip(" ,;:-"), True
                break
        rest = self._blank_end.sub(r", \1", rest)  # "yes sorry" is "yes, sorry" (round 39 callers: it was unclear)
        end = self._unsure_end.search(rest)  # round 44: "money I guess" is "money, I guess"; "yeah I guess", "stuff I guess" stay whole
        if end and set(tokenize(rest[:end.start()])) - self._plain:
            rest = f"{rest[:end.start()]}, {end.group(1)}"
        rest = self._tag_end.sub("", rest)  # round 53: "ok if it works", "free tbh" were saved whole
        rest = self._flip.sub("", rest)  # round 28 callers: "no yeah" was heard as backing out
        lead = self._answer_lead.match(rest)
        if lead and tokenize(rest[lead.end():]):  # "is it ok to say quit my job?": the answer, its "?" asks leave
            rest = rest[lead.end():].rstrip(" ?")
        lead = self._filler_lead.match(rest)
        if lead and tokenize(rest[lead.end():]) and not self.asks(rest[lead.end():]):  # round 53: "like money" got
            rest = rest[lead.end():]  # "let me put it another way"; "like what?" still asks
        while (back := self._take_back.search(rest)) or (kept := self._fixed_in(rest)) is not None:
            rest = self._with_unit(rest[:back.start()], rest[back.end():]) if back else kept
            # "3k, no wait, more like 4k" -> "more like 4k": they took the first part back; cut again so
            # "wait, sorry, what's the price?" asks
        if tokenize(rest) != tokenize(text):  # what is left once cut is read like a whole reply: "I'd say quit",
            rest = short_form(rest, self._cfg) or rest  # "sorry, quit", "quit, what else" were bare "quit" and
            # ended the call (rounds 49, 50); "quit" alone is still leaving
        parts, acts = [], []
        cut = clauses(rest, self.breaks)
        for part in cut:
            part, led = self._unlead(part)
            act = "asks" if led else self._act(part, len(cut) > 1)
            if act == "said" and len(cut) > 1:  # round 47: "yeah. quit." and "quit lol" were "quit" the call
                part = short_form(part, self._cfg) or part
            parts.append(part)
            unsure = act == "rise" and (acts[-1:] == ["hedge"] or self._unsure.match(part))
            acts.append("said" if unsure else act)  # "lol idk, money?", "I guess my car loan?": unsure, not asking
        if len(cut) > 1 and set(tokenize(rest)) <= self._plain:  # round 47: "yeah, ok" lost its "yeah" and was unclear;
            acts = ["said" if a == "tag" else a for a in acts]    # with no content beside it, a tag is the reply
        return Reply(text, rest, nudged, tuple(map(Part, parts, acts)))

    def _unlead(self, part):
        """A part opening with a polite lead (`ask_leads`: "I was wondering how this works") is the question
        after it, heard alone: ("how this works?", True); else (part, False)."""
        lead = self._ask_lead.match(part)
        if not lead or not tokenize(part[lead.end():]):
            return part, False
        return part[lead.end():].rstrip(" ?") + "?", True

    def asks(self, part):
        """Phrased as a question: it opens like one ("is this legit", "how much is it"), or it ends in "?" and
        starts with a question word or a helper verb ("what?", "is it?")."""
        words = tokenize(part)
        first = words[0] if words else ""
        said_as = {first, first.split("'")[0], first.removesuffix("s")}  # "what's", "whats" -> what
        return opens_question(part, self.cfg) or (part.rstrip().endswith("?") and bool(said_as & self._starts))

    def _act(self, part, several):
        if " ".join(w for w in tokenize(part) if w not in self._tag_skip) in self._tags:
            return "tag"
        if self.asks(part):
            return "asks"
        if part.rstrip().endswith("?"):
            return "rise"
        if several and (self._hedges(part) or self._aside.match(part) or set(tokenize(part)) <= self._blank):
            return "hedge"  # a reply that is only a hedge is a shrug: heard whole (shrug.py); "sorry for the long
            # message" says nothing on its own either, nor "sorry" or "lol" beside an answer ("yes, sorry")
        return "said"
