"""Fill {blanks} in a script line: offer blanks from the offer, prospect blanks with their own words by rule."""

import logging
import re
from difflib import get_close_matches
from functools import lru_cache

from core.buy_mode.script_engine.words.tone import PAUSE
from core.infra.loader import CONFIG_DIR
from core.infra.utils import tokenize

logger = logging.getLogger("script_engine.fallback")
NAME = re.compile(r"\{(\w+)(?:\|([^|{}]*)\|([^|{}]*))?\}")  # {name} or {name|noun form|verb form}, $ = the phrase
CENSORED = re.compile(r"\S*\w\*+\w*\S*")  # a word with stars in it ("f***ing"): never said back
WORD = re.compile(r"[$£€]?\d+(?:[.,]\d+)*%?[A-Za-z0-9'-]*|[A-Za-z0-9'-]+")  # "£2,500", "1.5", "2.5k", "50%" stay one word
FIGURE = re.compile(r"\d+(?:\.\d+)?")
GLUED = re.compile(r"(\d)([A-Za-z])")  # a number stuck to its unit: "1yr", "18mo"
MONEY_SIGNS = re.compile(r"(?<![\w£$€])[£$€]{2,}(?![\w£$€])")  # "£££", "$$$": a word for money, never a number
EMPHASIS = re.compile(r"(?<!\w)([*_`]+)(?=\S)([^*_`\n]+?)(?<=\S)\1(?!\w)")  # "**more money**": a pair, so "f***ing" stays
STRUCK = re.compile(r"(~+)(?=\S)[^~\n]+?(?<=\S)\1\s*")  # "~a year~ two years": taken back as they typed it
SENTENCE_END = re.compile(r"[.!?]+\s+|\s*\n\s*|(?:^|\s)(?:\d{1,2}[.)]|[-*•])\s+(?=[^\W\d])")  # "more money. Mostly for my kids": "2.5k" and "5k." stay whole
# A new line or a list mark ("1. more money 2. more time", "- pay rent") ends a sentence too: whole calls, "with 1?"


def blanks(line):
    """The names of the {blanks} in a line."""
    return {m.group(1) for m in NAME.finditer(line or "")}


def offer_blanks(offer):
    values = {"months": str(offer.months), "price": offer.price, "industry": offer.industry}
    if offer.setter:  # unset: the line with {setter} falls back to its plain line
        values["setter"] = offer.setter
    values.update({f"pillar_{i}": p for i, p in enumerate(offer.pillars, 1)})
    return values


@lru_cache(maxsize=None)
def real_words(filename):
    """The English words in config/`filename` (one a line, "#" lines are notes)."""
    lines = (CONFIG_DIR / filename).read_text(encoding="utf-8").splitlines()
    return frozenset(w.strip().lower() for w in lines if w.strip() and not w.startswith("#"))


def spell(word, vocab, cfg):
    """A typo turned into the script word it is plainly meant to be ("financialy" -> "financial", "mroe" -> "more").
    Known, short or unmatched words (names, places) stay as they are, and so does a real word that is
    just not in the script ("drown" is never "down")."""
    lower, real = word.lower(), real_words(cfg["spell_real_words"])
    if lower in vocab or any(c.isdigit() for c in lower) or lower in real:
        return word  # a figure ("2,500pm") is never a typo
    swaps = {lower[:i] + lower[i + 1] + lower[i] + lower[i + 2:] for i in range(1, len(lower) - 1)}  # the first letter is
    # rarely the slip, and keeping it keeps slang whole: "ive" is not "vie", "abt" is not "bat"
    swapped = swaps & vocab  # only into a script word: the real words hold names and letters too ("mam" is not "mma")
    if len(swapped) == 1 and len(lower) >= cfg["spell_swap_min_letters"]:
        return swapped.pop()  # two letters typed the wrong way round: "mroe", "yse"
    if len(lower) < cfg["spell_min_letters"]:
        return word
    if any(lower.endswith(end) and lower[:-len(end)] in vocab for end in cfg["spell_word_endings"]):
        return word  # "months", "works": a real word ending, not a typo
    near = get_close_matches(lower, vocab, 1, cfg["spell_cutoff"])
    if not near or near[0][len(lower):] in cfg["spell_word_endings"] and near[0].startswith(lower):
        return word  # "month" is not a typo of "months"
    return near[0]


def fix_typos(text, vocab, cfg):
    """The reply with plain typos fixed before it is understood ("monthy income" -> "monthly income", "£££" ->
    "money");
    punctuation and every other word kept as typed. A reply of one short form alone (`short_replies`: "y")
    is its word ("yes"): inside a reply, "y" is more often a year ("2 y")."""
    text = (text or "").strip()
    word = text.rstrip("?!.").lower()
    if word in cfg["short_replies"]:
        return cfg["short_replies"][word] + text[len(word):]
    text = MONEY_SIGNS.sub(cfg["money_signs_as"], text)  # "more £££" -> "more money": round 28, said back as "with more?"
    text = EMPHASIS.sub(r"\2", STRUCK.sub("", text))  # round 30: "with more?", and "~a year~ two years" was a year
    return WORD.sub(lambda m: spell(m.group(0), vocab, cfg), text)


def base_verb(word, cfg):
    """A goal's -ing word as the verb it comes from ("paying" -> "pay", "living" -> "live", "getting" -> "get");
    None when it is not one of the goal verbs."""
    lower = word.lower()
    if not lower.endswith("ing"):
        return None
    stem = lower[:-3]
    doubled = stem[:-1] if len(stem) > 2 and stem[-1] == stem[-2] else None
    return next((v for v in (stem, stem + "e", doubled) if v in cfg["verb_goal_starts"]), None)


def _after_want(words, cfg):
    """The words after who wants it ("my family needs", "we want", "my wife and I would like"): the goal, said
    back without them. Only near the start, and never past a "not" ("I don't want to work") or a "who"."""
    lower = [w.lower() for w in words]
    for i in range(min(len(lower), cfg["echo_want_within"] + 1)):
        if lower[i] in ("not", "never", *cfg["question_words"]) or lower[i].endswith("n't"):
            return words  # "people who want more": not who wants it
        want = next((len(w) for w in map(tokenize, cfg["echo_want_words"]) if lower[i:i + len(w)] == w), 0)
        if want and i + want < len(lower) and lower[i + want] in cfg["echo_want_objects"]:
            want += 1  # "my husband wants me to earn more" -> "to earn more"
        if want:
            return words[i + want:] if i else words  # at the very start ("need more money") it is the goal itself
    return words


def echo_phrase(reply, cfg, vocab=frozenset(), verbs=False):
    """Their own words for a blank, by rule, no AI: lead-ins like "I want" and hedges like "I guess" dropped
    ("I want more time I guess" -> "more time"), first person turned to second ("my kids" -> "your kids"). None when the words would
    not read right in the line: too long, no goal ("nothing"), or still speaking as the prospect. Only their
    first sentence is said back, up to any `echo_cut_at` word ("but").
    `verbs`: the blank has a verb form, so a goal they put as "-ing" or as a state is made a verb for it
    ("paying the bills" -> "pay the bills", "debt free" -> "be debt free")."""
    sentences = SENTENCE_END.split((reply or "").strip())  # one sentence, the first with more than filler ("fine.
    # more money"): whole calls, "with more money Mostly for your kids?"
    reply = next((x for x in sentences if set(tokenize(x)) - set(cfg["filler_words"])), sentences[0])
    cut = "|".join(map(re.escape, cfg["echo_cut_at"]))
    reply = re.split(rf"\b(?:{cut})\b", reply, maxsplit=1, flags=re.IGNORECASE)[0]  # "quit my job but I'm scared"
    if reply and reply.isupper() and len(tokenize(reply)) > 1:
        reply = reply.lower()  # shouted ("I WANT TO BE RICH!!!"): never said back in capitals ("BE RICH?")
    words = WORD.findall(CENSORED.sub(" ", reply or ""))  # "more f***ing money" -> "more money"
    words = [w for w in _after_want(words, cfg) if w.lower() not in cfg["echo_drop_words"]]  # "more money" from "my family needs more money"
    drops = [tokenize(d) for d in [*cfg["echo_drop_starts"], *cfg["filler_words"]]]  # "for sure, more money"
    cut = True
    while cut:
        lower = [w.lower() for w in words]
        cut = max((len(d) for d in drops if lower[:len(d)] == d), default=0)  # the longest: "so i can", not "so"
        words = words[cut:]
    for end in (tokenize(e) for e in cfg["echo_drop_ends"]):
        if [w.lower() for w in words[-len(end):]] == end:
            words = words[:-len(end)]
    if verbs and words:
        if verb := base_verb(words[0], cfg):
            words = [verb, *words[1:]]
        elif words[-1].lower() in cfg["be_goal_words"] and words[0].lower() not in cfg["verb_goal_starts"]:
            words = ["be", *words]
    swap = cfg["echo_pronoun_swap"]
    words = [swap.get(w.lower(), spell(w, vocab, cfg)) for w in words]
    lower = [w.lower() for w in words]
    known = vocab | real_words(cfg["spell_real_words"])
    if (not words or len(words) > cfg["slot_words"] or lower[0] in cfg["bad_phrase_starts"]
            or set(lower) & {*cfg["prospect_pronouns"], *cfg["echo_not_with"]}
            or any(w.isalpha() and w.islower() and len(w) > 2 and w not in known for w in words)):
        return None  # a typo still in it is never said back ("being able to mak more mony?"); a Name can be
    if words[0] == reply.lstrip()[:len(words[0])]:
        words[0] = words[0].lower()  # sentence case at the start of their reply, not a name
    listed = {m.group().lower() for m in WORD.finditer(reply) if reply[m.end():m.end() + 1] == ","}
    return " ".join(w + "," if w.lower() in listed and i < len(words) - 1 else w for i, w in enumerate(words))  # "money, time and travel"


def number_phrase(reply, rule, cfg):
    """The number before the blank's unit, as digits, by rule: "about 5 years now" -> "5", "a year" -> "1".
    None when no number sits right before the unit ("ages", "6 months" for a years blank). "and a half"
    (`number_half`) before or after the unit adds a half; a singular unit on its own opens a reply as one
    ("year and a half"), a part (`number_parts`) before it takes that share ("half a year" -> 6 months), and a number stuck to its unit is read apart ("1yr"). With `per`, the number is converted: "2 years" -> "24" for a months blank ("24 months" with `unit`). With
    `unit` ([one, many]), the unit is said after it: "1 year", "2 years", "a year and a half". A rule with
    `from` and no `units` takes that rule's units."""
    units = rule.get("units") or cfg["number_blanks"][rule["from"]]["units"]
    per, unit, half = rule.get("per"), rule.get("unit"), tokenize(cfg["number_half"])
    words = WORD.findall(GLUED.sub(r"\1 \2", reply or ""))  # "1yr" -> "1 yr"
    lower = [w.lower() for w in words if w.lower() not in cfg["number_skip"]]
    for i, word in enumerate(lower):
        if word not in (per or units):
            continue
        halved = lower[i + 1:i + 1 + len(half)] == half or (i > len(half) and lower[i - len(half):i] == half)
        at = i - 1 - (len(half) if halved and lower[i - len(half):i] == half else 0)
        count = _count(lower[at], cfg) if at >= 0 else (1 if not word.endswith("s") else None)
        if count is None:
            continue
        part = lower[at - 1] if at >= 1 and lower[at - 1] in cfg["number_parts"] else ""  # "half a year"
        value = count * cfg["number_parts"].get(part, 1) + (0.5 if halved else 0)
        if per:
            value *= per[word]
            return f"{value:g} {unit[value != 1]}" if unit else f"{value:g}"
        if not unit:
            return f"{value:g}"
        if part:
            return f"{part} {lower[at]} {unit[0]}"
        if halved:
            return f"a {unit[0]} and a half" if count == 1 else f"{count:g} and a half {unit[1]}"
        return f"{count:g} {unit[count != 1]}"
    return None


def _count(word, cfg):
    """A number said in digits or words ("3", "1.5", "three", "a"), else None."""
    return float(word) if FIGURE.fullmatch(word) else cfg["number_words"].get(word)


def is_verb_goal(phrase, cfg, said=""):
    """True when the phrase starts with a verb: one of `verb_goal_starts` ("be your own boss"), or any word
    they put after a `verb_goal_leads` word (`said`: "I want to replace my salary", "so I can cut down my hours";
    whole calls: "achieve with replace your salary")."""
    first = tokenize(phrase)[:1]
    leads = "|".join(map(re.escape, cfg["verb_goal_leads"]))
    return bool(first) and (first[0] in cfg["verb_goal_starts"]
                            or bool(re.search(rf"\b(?:{leads})\s+{re.escape(first[0])}\b", said or "", re.IGNORECASE)))


class Filler:
    """Turns script lines into spoken text: offer blanks from the offer, the prospect's own words (echo blanks)
    by rule. No AI, so the same line with the same answers always reads the same."""

    def __init__(self, cfg, offer, echo=frozenset(), vocab=frozenset()):
        self.cfg, self.offer, self.echo, self.vocab = cfg, offer, echo, vocab
        self._said = {}

    def fill(self, line, slots):
        """The line with every blank filled, or None if a prospect blank can't be."""
        values = offer_blanks(self.offer)
        forms = {m.group(1): m.group(2, 3) for m in NAME.finditer(line)}
        for blank in forms.keys() - values.keys():
            numbers = self.cfg["number_blanks"]
            reply = slots.get(numbers.get(blank, {}).get("from", blank))
            if not reply:
                phrase = None
            elif blank in numbers:
                phrase = number_phrase(reply, numbers[blank], self.cfg)
            else:
                phrase = self._echo(blank, forms[blank], slots) if blank in self.echo else None
            if phrase is None:
                return None
            noun, verb = forms[blank]
            form = (verb if is_verb_goal(phrase, self.cfg, reply) else noun) if noun is not None else "$"
            values[blank] = form.replace("$", phrase)
            for wordy, plain in self.cfg["form_joins"].items():  # "by being able to be rich" -> "by being rich"
                values[blank] = values[blank].replace(wordy, plain)
        return NAME.sub(lambda m: values.get(m.group(1), m.group(0)), line)

    def echoes(self, line, slots):
        """Their own phrases `line` would say back (its echo blanks, filled); [] when none, or it can't be filled."""
        if not line or self.fill(line, slots) is None:
            return []
        forms = {m.group(1): m.group(2, 3) for m in NAME.finditer(line)}
        return [self._echo(n, forms[n], slots) for n in sorted(forms.keys() & self.echo) if slots.get(n)]

    def _echo(self, blank, forms, slots):
        """Their words for one echo blank; made a verb when the blank has a verb form."""
        return echo_phrase(slots[blank], self.cfg, self.vocab, verbs=forms[0] is not None)

    def render(self, say, ack, say_plain, slots):
        """A step's final text (ack + line). Falls back to say_plain / no ack, and says so in the log."""
        key = (say, ack, tuple(sorted(slots.items())))
        if key not in self._said:
            text = self.fill(say, slots)
            if text is None:
                logger.warning("fallback to plain line for: %s", say)
                text = self.fill(say_plain, slots)
            lead = self.fill(ack, slots) if ack else ""
            if lead is None:
                logger.warning("dropped ack for: %s", ack)
                lead = ""
            gap = "" if lead.endswith(PAUSE) else " "  # a lead in its own bubble ("Damn.¶") needs no space
            self._said[key] = f"{lead}{gap}{text}".strip()
        return self._said[key]
