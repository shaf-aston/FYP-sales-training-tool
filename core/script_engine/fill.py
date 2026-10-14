"""Fill {blanks} in a script line: offer blanks from the offer, prospect blanks with their own words by rule."""

import logging
import re

from core.utils import tokenize

logger = logging.getLogger("script_engine.fallback")
NAME = re.compile(r"\{(\w+)(?:\|([^|{}]*)\|([^|{}]*))?\}")  # {name} or {name|noun form|verb form}, $ = the phrase
WORD = re.compile(r"[A-Za-z0-9'-]+")


def offer_blanks(offer):
    blanks = {"months": str(offer.months), "price": offer.price}
    blanks.update({f"pillar_{i}": p for i, p in enumerate(offer.pillars, 1)})
    return blanks


def echo_phrase(reply, cfg):
    """Their own words for a blank, by rule, no AI: lead-ins like "I want" dropped ("I want more time"
    -> "more time"), first person turned to second ("my kids" -> "your kids"). None when the words would
    not read right in the line: too long, no goal ("nothing"), or still speaking as the prospect."""
    words = WORD.findall(reply or "")
    drops = [tokenize(d) for d in cfg["echo_drop_starts"]]
    cut = True
    while cut:
        lower = [w.lower() for w in words]
        cut = next((len(d) for d in drops if lower[:len(d)] == d), 0)
        words = words[cut:]
    swap = cfg["echo_pronoun_swap"]
    words = [swap.get(w.lower(), w) for w in words]
    lower = [w.lower() for w in words]
    if (not words or len(words) > cfg["slot_words"] or lower[0] in cfg["bad_phrase_starts"]
            or set(lower) & set(cfg["prospect_pronouns"])):
        return None
    if words[0] == reply.lstrip()[:len(words[0])]:
        words[0] = words[0].lower()  # sentence case at the start of their reply, not a name
    return " ".join(words)


def is_verb_goal(phrase, cfg):
    """True when the phrase starts with a verb: "be your own boss", "quit your job"."""
    return tokenize(phrase)[:1] != [] and tokenize(phrase)[0] in cfg["verb_goal_starts"]


class Filler:
    """Turns script lines into spoken text: offer blanks from the offer, the prospect's own words (echo blanks)
    by rule. No AI, so the same line with the same answers always reads the same."""

    def __init__(self, cfg, offer, echo=frozenset()):
        self.cfg, self.offer, self.echo = cfg, offer, echo
        self._said = {}

    def fill(self, line, slots):
        """The line with every blank filled, or None if a prospect blank can't be."""
        values = offer_blanks(self.offer)
        forms = {m.group(1): m.group(2, 3) for m in NAME.finditer(line)}
        for blank in forms.keys() - values.keys():
            reply = slots.get(blank)
            phrase = echo_phrase(reply, self.cfg) if reply and blank in self.echo else None
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
