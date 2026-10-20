"""Fill {blanks} in a script line: offer blanks from the offer, prospect blanks with their own words by rule."""

import logging
import re
from difflib import get_close_matches

from core.utils import tokenize

logger = logging.getLogger("script_engine.fallback")
NAME = re.compile(r"\{(\w+)(?:\|([^|{}]*)\|([^|{}]*))?\}")  # {name} or {name|noun form|verb form}, $ = the phrase
WORD = re.compile(r"[A-Za-z0-9'-]+")


def offer_blanks(offer):
    blanks = {"months": str(offer.months), "price": offer.price}
    blanks.update({f"pillar_{i}": p for i, p in enumerate(offer.pillars, 1)})
    return blanks


def spell(word, vocab, cfg):
    """A typo turned into the script word it is plainly meant to be ("financialy" -> "financial").
    Known, short or unmatched words (names, places) stay as they are."""
    lower = word.lower()
    if lower in vocab or len(lower) < cfg["spell_min_letters"]:
        return word
    if any(lower.endswith(end) and lower[:-len(end)] in vocab for end in cfg["spell_word_endings"]):
        return word  # "months", "works": a real word ending, not a typo
    near = get_close_matches(lower, vocab, 1, cfg["spell_cutoff"])
    if not near or near[0][len(lower):] in cfg["spell_word_endings"] and near[0].startswith(lower):
        return word  # "month" is not a typo of "months"
    return near[0]


def fix_typos(text, vocab, cfg):
    """The reply with plain typos fixed before it is understood ("monthy income" -> "monthly income");
    punctuation and every other word kept as typed."""
    return WORD.sub(lambda m: spell(m.group(0), vocab, cfg), text or "")


def echo_phrase(reply, cfg, vocab=frozenset()):
    """Their own words for a blank, by rule, no AI: lead-ins like "I want" and hedges like "I guess" dropped
    ("I want more time I guess" -> "more time"), first person turned to second ("my kids" -> "your kids"). None when the words would
    not read right in the line: too long, no goal ("nothing"), or still speaking as the prospect."""
    words = WORD.findall(reply or "")
    drops = [tokenize(d) for d in cfg["echo_drop_starts"]]
    cut = True
    while cut:
        lower = [w.lower() for w in words]
        cut = next((len(d) for d in drops if lower[:len(d)] == d), 0)
        words = words[cut:]
    for end in (tokenize(e) for e in cfg["echo_drop_ends"]):
        if [w.lower() for w in words[-len(end):]] == end:
            words = words[:-len(end)]
    swap = cfg["echo_pronoun_swap"]
    words = [swap.get(w.lower(), spell(w, vocab, cfg)) for w in words]
    lower = [w.lower() for w in words]
    if (not words or len(words) > cfg["slot_words"] or lower[0] in cfg["bad_phrase_starts"]
            or set(lower) & set(cfg["prospect_pronouns"])):
        return None
    if words[0] == reply.lstrip()[:len(words[0])]:
        words[0] = words[0].lower()  # sentence case at the start of their reply, not a name
    return " ".join(words)


def number_phrase(reply, rule):
    """The number before the blank's unit, by rule: "about 5 years now" -> "5", "two years" -> "two".
    None when no number sits right before the unit ("ages", "6 months" for a years blank)."""
    lower = [w.lower() for w in WORD.findall(reply or "")]
    for before, word in zip(lower, lower[1:]):
        if word in rule["units"] and (before.isdigit() or before in rule["words"]):
            return before
    return None


def is_verb_goal(phrase, cfg):
    """True when the phrase starts with a verb: "be your own boss", "quit your job"."""
    return tokenize(phrase)[:1] != [] and tokenize(phrase)[0] in cfg["verb_goal_starts"]


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
            reply = slots.get(blank)
            numbers = self.cfg["number_blanks"]
            if not reply:
                phrase = None
            elif blank in numbers:
                phrase = number_phrase(reply, numbers[blank])
            else:
                phrase = echo_phrase(reply, self.cfg, self.vocab) if blank in self.echo else None
            if phrase is None:
                return None
            noun, verb = forms[blank]
            form = (verb if is_verb_goal(phrase, self.cfg) else noun) if noun is not None else "$"
            values[blank] = form.replace("$", phrase)
        return NAME.sub(lambda m: values.get(m.group(1), m.group(0)), line)

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
            self._said[key] = f"{lead} {text}".strip()
        return self._said[key]
