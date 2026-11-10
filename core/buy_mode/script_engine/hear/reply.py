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
import unicodedata
from dataclasses import dataclass, replace
from itertools import takewhile

from core.buy_mode.script_engine.config import plain_words
from core.buy_mode.script_engine.words.fill import number_phrase, short_form
from core.infra.utils import normal, opens_question, tokenize


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
                return _span(self.unnudged, kept).rstrip(" ?")  # a "?" on what they said goes, as when parts are joined
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


def _span(text, parts):
    """The reply as typed, from its first part on: a break word before it goes, and marks and emoji on the end
    (round 76 callers: "so 2k", "money!!" and "money 🙂" were saved whole; "I think so" keeps its "so").
    The parts joined when the first was reworded ("so, quit" -> "quit my job")."""
    start = text.find(parts[0].text)
    if start < 0:
        return ", ".join(p.text for p in parts)
    kept = text[start:]
    return kept.rstrip("".join(c for c in set(kept) if unicodedata.category(c) in ("So", "Mn")) + " !.…") or kept


def break_pattern(cfg):
    """The one place a reply is cut: at `clause_breaks` (punctuation only before a space or the end, so "2.5k"
    stays whole, and a comma also before a letter: "more money,more time"; words as whole words)."""
    ends = {",": r"(?=\s|$|[^\W\d])"}

    def keep(b):  # round 74: "thanks so much" was "thanks" and "much"; round 76: a pair ("so that") keeps that break only
        words = [w.split(maxsplit=1)[-1] for w in cfg["break_not_before"] if " " not in w or w.split()[0] == b]
        return rf"(?!\W+(?:{'|'.join(r'\W+'.join(map(re.escape, w.split())) for w in words)})\b)" if words else ""  # round 92: "and a half"
    parts = [rf"\b{re.escape(b)}\b{keep(b)}" if b.isalpha() else re.escape(b) + ends.get(b, r"(?=\s|$)") for b in cfg["clause_breaks"]]
    if cfg["ask_tails"]:  # round 77: "yes why?" is read as "yes, why?"
        never = "".join(rf"(?<!\b{re.escape(w)})" for w in cfg["ask_tails_not_after"])  # round 78 mutation: "I don't know why?" is not knowing
        parts.append(rf"(?<!\s){never}\s+(?=(?:{'|'.join(map(re.escape, cfg['ask_tails']))})\s*\?)")
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
        self._subjects = set(cfg["nudge_subjects"])
        broken = set(cfg["nudge_after_break"])   # "what happens next?" keeps its "next"; "debit, next" does not
        self._nudges = [re.compile(rf"(?:^|{r'[^\w\s]' if p in broken else ''}\W)(?:(?:{leads})\W+)?{words}\W*$", re.IGNORECASE)
                        for p, words in ((p, r"\W+".join(map(re.escape, tokenize(p)))) for p in sorted(nudges, key=len, reverse=True))]
        self._tags = {normal(t) for t in [*cfg["filler_tags"], *cfg["end_tags"]]}
        self._tag_skip = frozenset(cfg["tag_skip"])  # "to be completely honest" is "to be honest"
        self._starts = set(cfg["question_words"]) | set(cfg["closed_question_starts"])
        self._question_words = set(cfg["question_words"])
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
        self._unsure_said = {normal(u) for u in [*cfg["unsure_ends"], *cfg["shrug_leads"]]}  # round 73: "I daresay, money" was saved whole
        # round 85 callers: "nae idea, money" too (a shrug its meaning alone missed)
        # round 76: after a dash too ("free - i guess" was saved whole)
        self._unsure_end = re.compile(rf"(?<=\w)(?:\s+[–—-])?\s+((?:{any_of(cfg['unsure_ends'])})\W*)$", re.IGNORECASE)
        self._plain = plain_words(cfg)
        alone = {w for t in cfg["tags_alone_mean"] for w in tokenize(t)}
        self._alone_mean = self._plain | alone  # round 73: "meh, whatever"
        self._lead_asks = set(cfg["question_leads"])
        self._you = set(cfg["asked_back_you"])
        self._lead_alone = alone - self._plain  # round 74: a lead with a meaning alone ("thanks", "brb")
        self._no = set(cfg["no_words"])
        self._okay_end = re.compile(rf"(?<=\w)[\s,;.!-]+(?:{any_of(cfg['okay_ends'])})\W*$", re.IGNORECASE)
        self._okay_not_after = set(cfg["stop_words"]) | set(cfg["okay_ends_not_after"])
        self._thanks_end = re.compile(rf"(?<=\w)\s+((?:{any_of(cfg['thanks_ends'])})\W*)$", re.IGNORECASE)
        self._thanks_lead = re.compile(rf"(?:{any_of(cfg['thanks_ends'])})\b", re.IGNORECASE)
        # round 61: after a comma too, so "2k, that kind of thing" loses the whole tag, not just "kind of thing"
        # round 73: every tag at the end, not just the last ("and so on and so forth", "yada yada tbh")
        # round 75: after a full stop, "!", "..." or a dash too ("a year. or so", "money - tbh" were saved whole)
        self._tag_end = re.compile(rf"(?<=\w)(?:\s*[,;.!…–—-]*\s+(?:{any_of(cfg['end_tags'])}))+\W*$", re.IGNORECASE)
        # round 73: "money yeah?", "free, no?", "money. no?": a check at the end asks nothing; "yes or no?" picks one
        self._check_end = re.compile(rf"(?<=\w)(?<!\bor)[,;.!]?\s+(?:{any_of(cfg['check_tags'])})\s*\?[\s?!.]*$", re.IGNORECASE)
        self._unsure = re.compile(rf"^\W*(?:{any_of(cfg['unsure_leads'])})\b", re.IGNORECASE)
        # round 64: the hedge stays whole only when that word ends the reply ("probably not"), so "probably yes for the money" is split
        self._unsure_lead = re.compile(rf"^\W*((?:{any_of(cfg['unsure_ends'])}))\s+(?!(?:{any_of(cfg['unsure_whole'])})\W*(?:$|[,.;!]))(?=\w)", re.IGNORECASE)
        not_before = any_of([*cfg["question_words"], *cfg["shrug_leads_not_before"]])  # round 84: "dunno my boss" was saved whole
        self._shrug_lead = re.compile(rf"^\W*((?:{any_of(cfg['shrug_leads'])}))\W+(?!(?:{not_before})\b)(?=\w)", re.IGNORECASE)
        self._aside = re.compile(rf"^\W*(?:{any_of(cfg['aside_starts'])})\b", re.IGNORECASE)
        self._aside_say = re.compile(rf"\b(?:{any_of(cfg['aside_says'])})\b", re.IGNORECASE)
        self._ask_lead = re.compile(rf"^\W*(?:{any_of(cfg['ask_leads'])})\b\W*", re.IGNORECASE)
        flips = "|".join(rf"{re.escape(a)}\W+(?={re.escape(b)}\s*(?:[,;.!?]|$))" for a, b in map(tokenize, cfg["flip_leads"]))
        self._flip = re.compile(rf"^\W*(?:{flips})", re.IGNORECASE)  # "no yeah" is a yes, "yeah no" a no: the last word counts
        joins = any_of([b for b in cfg["clause_breaks"] if b.isalpha()])  # round 79: "so like money" got "let me put it another way"
        self._shorts = shorts = {*cfg["short_replies"], *cfg["short_replies"].values()}  # round 82: "ok 2k" loses its "ok", "oh ok" keeps it
        fillers = any_of([f for f in cfg["filler_leads"] if f not in shorts])  # a break word only between fillers: "so that I can quit" stays whole
        fillers = rf"{fillers}|(?:{any_of([f for f in cfg['filler_leads'] if f in shorts])})(?=\W+\w)"
        self._filler_lead = re.compile(rf"^\W*(?:(?:{fillers})\b(?!\W+(?:{any_of(cfg['lead_not_before'])})\b)\W*|(?:{joins})\W+(?=(?:{fillers})\b))+",
                                       re.IGNORECASE)  # round 54: "oh wow ok" is "ok"; "well paid job" keeps its "well"
        self._answer_lead = re.compile(rf"^\W*(?:{any_of(cfg['answer_leads'])})\b\W*", re.IGNORECASE)
        self._answer_check = re.compile(rf"^\W*({any_of(cfg['answer_check_leads'])})\s+(\w.*?)\s+({any_of(cfg['answer_checks'])})\s*\?\W*$", re.IGNORECASE)
        self._report_lead = re.compile(rf"^\W*(?:{any_of(cfg['report_people'])})\s+(?:{any_of(cfg['report_verbs'])})\b\W*", re.IGNORECASE)
        self._take_back = re.compile(rf"(?:^|[,;.!?]\s*)(?:(?:{words})\b[\s,;.!-]*|(?:{word})\s*[,;.!-][\s,;.!-]*)(?=\w)"
                                     rf"|(?<=\w){not_mid}[,;.!?]\s*(?:{mid})\s*[,;.!-][\s,;.!-]*(?=\w)"
                                     rf"|(?<=\w)\s+(?:{any_of(cfg['take_backs_no_break'])})\b[\s,;.!-]*(?=\w)", re.IGNORECASE)

        # "2k, no 3k", "more time, sorry more money": between two answers of one kind a correction needs no break
        # after it (round 33/34 callers: the first was kept); "yes, sorry the baby was crying" is two kinds, so stays
        self._amount = re.compile(rf"\d\w*|(?:{any_of(cfg['number_words'])})", re.IGNORECASE)
        self._bare = re.compile(rf"\d+(?:[.,]\d+)?|(?:{any_of(cfg['number_words'])})", re.IGNORECASE)  # "2k" has its unit
        self._fix_back = re.compile(rf"(?<=\w){not_mid}[,;.!?]\s*(?:{mid}|{word})\s+(?=\w)", re.IGNORECASE)
        self._fix_bare = re.compile(rf"(?<=\w){not_mid}\s+(?:{mid}|{word})\s+(?=\w)", re.IGNORECASE)  # "2k sorry 3k"
        self._denied = re.compile(rf"^\W*(?:{any_of(cfg['denied_leads'])})\s+(?=\w)", re.IGNORECASE)  # "not a year, two"
        self._any_kind = {normal(w) for w in cfg["fix_any_kind"]}  # round 91: "money, actually time"
        self._kept = self._plain | set(cfg["fix_kept_words"])  # "not today, tomorrow" asks for time, so stays whole
        self._address_end = re.compile(rf"(?<=\w)\s*[,;.!…–—-]+\s*(?:{any_of(cfg['address_ends'])})\W*$", re.IGNORECASE)
        self._marks = re.compile(r"[?!]*\?[?!]*(?=\s|$)")
        never = "".join(rf"(?<!\b{re.escape(w)})" for w in cfg["dictated_not_after"])  # "a short period" keeps it
        self._dictated = re.compile(rf"(?<=\w){never}\s+({any_of(cfg['dictated_marks'])})\b(?=\s*$|\s+\w)", re.IGNORECASE)
        self._marks_said = {normal(k): v for k, v in cfg["dictated_marks"].items()}
        # round 92 callers: "money, hold on" lost the money (heard as a pause) and "money, actually" was said back:
        # a take-back after a break with nothing after it takes nothing back; "yes, hold on" and "hold on" stay whole
        self._back_end = re.compile(rf"(?<=\w)\s*[,;.!…–—-]+\s*(?:{word})\W*$", re.IGNORECASE)
        self._bracket_end = re.compile(r"(?<=\S)\s*\(([^()]*)\)\W*$")
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
        bare = None if back else self._fix_bare.search(text)  # round 86 callers: "2k sorry 3k" was saved whole; with no
        if bare and self._figure(text[:bare.start()]) and self._figure(text[bare.end():]):  # comma, only between figures
            back = bare
        cut = clauses(text[denied.end():], self.breaks) if denied else []
        if not back and len(cut) < 2:
            return None
        taken = text[:back.start()] if back else cut[0]  # "not a year, two": the year is denied, two is kept
        before, new = tokenize(clauses(taken, self.breaks)[-1]), text[back.end():].strip() if back else after(text, cut[0])
        swap = (denied or normal(back.group()) in self._any_kind) and len(before) == len(tokenize(new)) <= 2
        if not ((self._figure(" ".join(before)) and self._figure(new)) or before[:1] == tokenize(new)[:1]
                or (swap and not {*before, *tokenize(new)} & self._kept)):  # round 91 callers: "not money, time" and
            return None  # "money, actually time" were said back whole; "not really, busy" and "money, actually quite a lot" stay
        return self._with_unit(taken, new)

    def _with_unit(self, taken, new):
        """The words kept after a correction. A bare amount keeps the unit said after the first one: "a year,
        well two" -> "two year" (round 50 callers: "a year, no, two" was a bare "two" and missed)."""
        last = clauses(taken, self.breaks)
        before = tokenize(last[-1]) if last else []
        said = [i for i, w in enumerate(before) if self._amount.fullmatch(w)]
        bare = said and all(self._bare.fullmatch(w) for w in tokenize(new))  # "a million, jk, 2k": 2k
        unit = takewhile(lambda w: w not in self.cfg["number_range_joins"], before[said[-1] + 1:]) if bare else ()
        return " ".join([new.rstrip(" .!;:"), *unit]) if bare else new  # round 94 callers: "A year. Closer to two." was
        # "two. year", and "a year or closer to two" was "two year or"

    def _own_words(self, before):
        """The words before a nudge say who does it ("I keep going", "we carry on"): the nudge is their answer.
        Round 105 callers: "I keep going" to "What makes you different?" was cut to "I" and asked again."""
        return not re.search(r"[^\w\s']\W*$", before) and bool(set(tokenize((clauses(before, self.breaks) or [""])[-1])) & self._subjects)

    def read(self, text):
        rest = marked = self.squash(text)
        nudged = False
        for nudge in self._nudges:
            found = nudge.search(marked)
            if found and not self._own_words(marked[:found.start()]):
                rest, nudged = marked[:found.start()].rstrip(" ,;:-"), True
                break
        aside = self._bracket_end.search(rest)  # round 76: "money (mostly)", "a year (sorry)" were saved whole;
        if aside and self._act(aside.group(1), True) in ("tag", "hedge"):
            rest = rest[:aside.start()]  # "quit (my job)" and "2k (maybe more)" keep theirs
        cut = clauses(rest, self.breaks)  # round 95 callers: "quit my job, sorry, kids are loud" was saved as "kids are
        kept = [c for c in cut if not self._aside_say.search(c)]  # loud" ("sorry" took the answer back), "2k, sorry,
        if len(kept) < len(cut) and set(tokenize(" ".join(kept))) - self._plain:  # where was I" got "let me say that
            rest = ", ".join(kept)  # again": an aside beside an answer is left out ("sorry, where was I?" still asks)
        if self._act(rest, False) == "tag":  # full run 84: a whole tag is one part, never cut ("so to speak" was "to speak",
            return Reply(text, rest, nudged, (Part(rest, "tag"),))  # "like everyone" "everyone", "for me personally" "for me")
        first = (clauses(rest, self.breaks) or [""])[0]
        if len(tokenize(first)) > 1 and self._act(first, False) == "tag" and set(tokenize(after(rest, first))) - self._plain:
            rest = after(rest, first)  # round 84 callers: "like everyone, money" was saved as "everyone, money"; "thanks a lot, 2k" keeps its thanks
        check = self._check_end.search(rest)  # "is it free, no?" and "credit, is that ok?" still ask; "yes, no?" is torn
        kept = rest[:check.start()] if check else ""
        if check and set(tokenize(kept)) - self._plain and not self.asks((clauses(kept, self.breaks) or [kept])[-1] + "?"):
            rest = kept
        rest = self._blank_end.sub(r", \1", rest)  # "yes sorry" is "yes, sorry" (round 39 callers: it was unclear)
        thanks = self._thanks_end.search(rest)  # round 82 callers: "2k thanks" was saved whole; "ok thanks", "no thanks" stay whole
        if thanks and set(tokenize(rest[:thanks.start()])) - self._alone_mean - self._no and tokenize(rest[:thanks.start()])[-1] not in self._no:
            rest = f"{rest[:thanks.start()]}, {thanks.group(1)}"
        okay = self._okay_end.search(rest)  # round 83 callers: "money ok", "2k k" were saved whole; "I'm doing ok" stays whole
        if (okay and set(before := tokenize(rest[:okay.start()])) - self._plain and before[-1] not in self._okay_not_after
                and not ((back := self._take_back.match(rest)) and back.end() > okay.start())):  # full run 85: "you know
            rest = rest[:okay.start()]  # what, ok" was saved as "you know what"; a take-back before the "ok" leaves it alone
        end = self._unsure_end.search(rest)  # round 44: "money I guess" is "money, I guess"; "yeah I guess", "stuff I guess" stay whole
        if end and set(tokenize(rest[:end.start()])) - self._plain:
            rest = f"{self._tag_end.sub('', rest[:end.start()])}, {end.group(1)}"  # round 75: "money or so i think" was "money or"
        lead = self._unsure_lead.match(rest)  # round 58: "probably money", "I guess money" got "What do you mean by
        if lead and set(tokenize(rest[lead.end():])) - self._plain:  # money?"; "I think so", "probably not" stay whole
            rest = f"{lead.group(1)}, {rest[lead.end():]}"
        lead = self._shrug_lead.match(rest)  # round 84 callers: "dunno my boss" as "dunno, my boss"; "dunno why" stays whole
        if lead and set(tokenize(rest[lead.end():])) - self._plain:
            rest = f"{lead.group(1)}, {rest[lead.end():]}"
        back = self._back_end.search(rest)
        if back and set(tokenize(rest[:back.start()])) - self._alone_mean:
            rest = rest[:back.start()]
        rest = self._address_end.sub("", rest)  # round 91 callers: "2k, mate" got "You're welcome"; "my mate" stays
        rest = self._tag_end.sub("", rest)  # round 53: "ok if it works", "free tbh" were saved whole
        rest = self._flip.sub("", rest)  # round 28 callers: "no yeah" was heard as backing out
        lead = self._report_lead.match(rest)  # round 87 callers: "my wife says money" was a partner worry; "my partner says no" stays
        if lead and set(tokenize(rest[lead.end():])) - self._alone_mean - self._no:
            rest = rest[lead.end():]
        # round 93 callers: "is money a good answer?" got "I'll find out"; now "money, is that a good answer?".
        # "is it enough?" and "is my goal realistic?" stay questions
        check = self._answer_check.match(rest)
        said = tokenize(check.group(2)) if check else []
        if said and set(said) - self._plain and said[0] not in self._cfg["stop_words"]:
            rest = f"{check.group(2)}, {check.group(1)} that {check.group(3)}?"
        lead = self._answer_lead.match(rest)
        if lead and tokenize(rest[lead.end():]):  # "is it ok to say quit my job?": the answer, its "?" asks leave
            rest = rest[lead.end():].rstrip(" ?")
        rest = self._unfill(rest)
        taken = rest
        while (back := self._take_back.search(rest)) or (kept := self._fixed_in(rest)) is not None:
            rest = self._with_unit(rest[:back.start()], rest[back.end():]) if back else kept
            # "3k, no wait, more like 4k" -> "more like 4k": they took the first part back; cut again so
            # "wait, sorry, what's the price?" asks
        if rest != taken:
            rest = self._unfill(rest)  # round 84 callers: "just a sec, actually 3k" was saved as "actually 3k"
        if tokenize(rest) != tokenize(text):  # what is left once cut is read like a whole reply: "I'd say quit",
            rest = short_form(rest, self._cfg) or rest  # "sorry, quit", "quit, what else" were bare "quit" and
            # ended the call (rounds 49, 50); "quit" alone is still leaving
        parts, acts = [], []
        cut = clauses(rest, self.breaks)
        for part in cut:
            part, led = self._unlead(part)
            act = "asks" if led else self._act(part, len(cut) > 1)
            if act == "said" and (len(cut) > 1 or part != rest):  # round 47: "yeah. quit." and "quit lol" were "quit" the call;
                part = short_form(part, self._cfg) or part  # round 76: "so, quit" too, once its "so" went
            parts.append(part)
            unsure = act == "rise" and (acts[-1:] == ["hedge"] or self._unsure.match(part)) and not self.turned_back(part)
            acts.append("said" if unsure else act)  # "lol idk, money?", "I guess my car loan?": unsure, not asking
        if len(cut) > 1 and set(tokenize(rest)) <= self._alone_mean:  # round 47: "yeah, ok" lost its "yeah" and was unclear;
            acts = ["said" if a == "tag" else a for a in acts]    # with no content beside it, a tag is the reply
        return Reply(text, rest, nudged, tuple(map(Part, parts, acts)))

    def _unfill(self, rest):
        """`rest` without a filler lead before an answer: "like money" is "money"; "like what?" still asks, "oh
        what?" is "what?" (round 80); "thanks mate" stays whole, "thanks, 2k" is "2k" (round 74)."""
        lead = self._filler_lead.match(rest)
        after = rest[lead.end():] if lead else ""
        if (lead and tokenize(after) and not (self.asks(after) and set(tokenize(lead.group())) & self._lead_asks)  # round 53: "like money" got "let me put it another way"
                and not (set(tokenize(lead.group())) & self._lead_alone and set(tokenize(after)) <= self._plain)
                and not (set(tokenize(lead.group())) & self._shorts and (set(tokenize(after)) <= self._alone_mean | self._blank or self._act(" ".join(w for w in tokenize(rest) if w not in self._shorts), False) == "tag"))):
            thanks = self._thanks_lead.match(rest)  # full run 84: "thanks for asking, 2 years" lost its thank-you;
            if thanks:  # now it goes last, as in "2 years, thanks"; round 86 callers: the whole of it ("cheers mate, 2k" was "mate, 2k, cheers")
                after = rest[thanks.end():].lstrip(" ,;:-.!")
                return f"{after}, {thanks.group()}" if tokenize(after) else rest
            return after
        return rest

    def turned_back(self, text):
        """"you?", "and you?", "u?": only a "you" and plain words, their question turned back on us. Round 81
        callers: "not sure, you?" got "No rush, even a rough idea helps" ("you" and "and" are stop words)."""
        words = set(tokenize(text))
        return bool(words & self._you) and words <= self._plain | self._you

    def squash(self, text):
        """A run of end marks with a "?" in it is one "?" (round 76 callers: "money?!" was a question it could not answer);
        a mark said as a word after a word is the mark (round 92 callers: voice to text, "more money period")."""
        text = self._dictated.sub(lambda m: self._marks_said[normal(m.group(1))], text)  # round 92: "money period"
        return self._marks.sub("?", text)

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
        asked_after = len(words) == 2 and words[1] in self._question_words  # round 87 probes: "since when?", "for what?"
        return opens_question(part, self.cfg) or (part.rstrip().endswith("?") and (bool(said_as & self._starts) or asked_after))

    def _act(self, part, several):
        if " ".join(w for w in tokenize(part) if w not in self._tag_skip) in self._tags:
            return "tag"
        if self.asks(part):
            return "asks"
        if part.rstrip().endswith("?"):
            return "rise"
        if several and (self._hedges(part) or normal(part) in self._unsure_said or self._aside.match(part)
                        or set(tokenize(part)) <= self._blank):
            return "hedge"  # a reply that is only a hedge is a shrug: heard whole (shrug.py); "sorry for the long
            # message" says nothing on its own either, nor "sorry" or "lol" beside an answer ("yes, sorry")
        return "said"
