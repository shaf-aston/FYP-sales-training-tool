"""Fill {blanks} in a script line. Offer blanks by code, prospect blanks by a checked AI phrase."""

import logging
import re

from core.script_engine.ai_line import checked_line
from core.script_engine.checks import BLANK, CheckContext
from core.utils import tokenize

logger = logging.getLogger("script_engine.fallback")
NAME = re.compile(r"\{(\w+)(?:\|([^|{}]*)\|([^|{}]*))?\}")  # {name} or {name|noun form|verb form}, $ = the phrase
WORD = re.compile(r"[A-Za-z0-9'-]+")


def offer_blanks(offer):
    blanks = {"months": str(offer.months), "price": offer.price}
    blanks.update({f"pillar_{i}": p for i, p in enumerate(offer.pillars, 1)})
    return blanks


def _phrase(line, blank, reply, cfg, llm):  # used by Filler only
    """AI shortens the reply to a phrase for one blank. Returns None if no attempt passes."""
    sentence = NAME.sub(lambda m: (m.group(2) or "$").replace("$", "____") if m.group(1) == blank else m.group(0), line)
    prompt = (
        "Fill the blank so the sentence reads naturally, like a person talking. Use a short noun "
        f"phrase (at most {cfg['slot_words']} words) made only of words the prospect said. "
        f"If nothing fits naturally, answer NONE.\nSentence: {sentence}\n"
        f"Prospect said: <reply>{reply}</reply>\n"
        "Answer with the phrase only."
    )
    ctx = CheckContext(
        max_words=cfg["slot_words"], questions=0, price_ok=True,
        prospect_words=frozenset(tokenize(reply)), stop_words=frozenset(cfg["stop_words"]),
    )
    before, _, after = sentence.partition("____")

    def clean(raw):
        phrase = raw.strip().strip("\"'.")
        return None if phrase.upper() == "NONE" else phrase

    def fits_the_line(phrase):
        said, broken = tokenize(phrase), []
        if said and said[0] in cfg["bad_phrase_starts"]:
            broken.append("starts_like_a_lead_in")  # "feel to stop working ..." breaks the line
        if set(said) & set(cfg["prospect_pronouns"]):
            broken.append("speaks_as_prospect")  # "got to my own business"
        if said and (said[-1:] == tokenize(after)[:1] or said[:1] == tokenize(before)[-1:]):
            broken.append("repeats_next_word")  # "feel travel X X"
        return broken

    return checked_line(llm, prompt, cfg["slot_tokens"], ctx, cfg, f"blank {blank}", clean, fits_the_line)


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
    """Turns script lines into spoken text: offer blanks by code, the buyer's own words (echo blanks) by
    rule, other prospect blanks by a checked AI phrase. The same line with the same answers reads the same."""

    def __init__(self, cfg, offer, llm, echo=frozenset()):
        self.cfg, self.offer, self.llm, self.echo = cfg, offer, llm, echo
        self._said = {}

    def fill(self, line, slots):
        """The line with every blank filled, or None if a prospect blank can't be."""
        values = offer_blanks(self.offer)
        forms = {m.group(1): m.group(2, 3) for m in NAME.finditer(line)}
        for blank in forms.keys() - values.keys():
            reply = slots.get(blank)
            phrase = echo_phrase(reply, self.cfg) if reply and blank in self.echo else None
            if phrase is None and reply and self.cfg["ai_fill_blanks"]:
                phrase = _phrase(line, blank, reply, self.cfg, self.llm)
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
