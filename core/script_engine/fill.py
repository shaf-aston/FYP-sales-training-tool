"""Fill {blanks} in a script line. Offer blanks by code, prospect blanks by a checked AI phrase."""

import logging
import re

from core.script_engine.ai_line import checked_line
from core.script_engine.checks import BLANK, CheckContext
from core.utils import tokenize

logger = logging.getLogger("script_engine.fallback")
NAME = re.compile(r"\{(\w+)\}")
WORD = re.compile(r"[A-Za-z0-9'-]+")


def offer_blanks(offer):
    blanks = {"months": str(offer.months), "price": offer.price}
    blanks.update({f"pillar_{i}": p for i, p in enumerate(offer.pillars, 1)})
    return blanks


def _phrase(line, blank, reply, cfg, llm):
    """AI shortens the reply to a phrase for one blank. Returns None if no attempt passes."""
    sentence = BLANK.sub(lambda m: "____" if m.group(0) == "{" + blank + "}" else m.group(0), line)
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
            broken.append("starts_like_a_verb")  # "feel to stop working ..." breaks the line
        if set(said) & set(cfg["prospect_pronouns"]):
            broken.append("speaks_as_prospect")  # "got to my own business"
        if said and (said[-1:] == tokenize(after)[:1] or said[:1] == tokenize(before)[-1:]):
            broken.append("repeats_next_word")  # "feel travel X X"
        return broken

    return checked_line(llm, prompt, cfg["slot_tokens"], ctx, cfg, f"blank {blank}", clean, fits_the_line)


def echo_phrase(reply, cfg):
    """Their own words for a blank, by rule, no AI: lead-ins like "I want" dropped ("I want more time"
    -> "more time"). None when the words would not read right in the line: too long, starting like a
    verb, or speaking as the prospect ("my own boss")."""
    words = WORD.findall(reply or "")
    drops = [tokenize(d) for d in cfg["echo_drop_starts"]]
    cut = True
    while cut:
        lower = [w.lower() for w in words]
        cut = next((len(d) for d in drops if lower[:len(d)] == d), 0)
        words = words[cut:]
    lower = [w.lower() for w in words]
    bad_starts = set(cfg["bad_phrase_starts"]) | set(cfg["echo_bad_starts"])
    if (not words or len(words) > cfg["slot_words"] or lower[0] in bad_starts
            or set(lower) & set(cfg["prospect_pronouns"])):
        return None
    if words[0] == reply.lstrip()[:len(words[0])]:
        words[0] = words[0].lower()  # sentence case at the start of their reply, not a name
    return " ".join(words)


def fill_line(line, slots, offer, cfg, llm, echo=frozenset()):
    """Return the line with every blank filled, or None if a prospect blank can't be.
    echo = blanks that may take the prospect's own words as they said them (tried before the AI)."""
    values = offer_blanks(offer)
    for blank in set(NAME.findall(line)) - values.keys():
        reply = slots.get(blank)
        phrase = echo_phrase(reply, cfg) if reply and blank in echo else None
        if phrase is None and reply and cfg["ai_fill_blanks"]:
            phrase = _phrase(line, blank, reply, cfg, llm)
        if phrase is None:
            return None
        values[blank] = phrase
    return NAME.sub(lambda m: values.get(m.group(1), m.group(0)), line)


def fill_step(say, ack, say_plain, slots, offer, cfg, llm, echo=frozenset()):
    """Fill a step's line (and its ack). Falls back to say_plain / no ack, and says so in the log."""
    text = fill_line(say, slots, offer, cfg, llm, echo)
    if text is None:
        logger.warning("fallback to plain line for: %s", say)
        text = fill_line(say_plain, slots, offer, cfg, llm, echo)
    lead = fill_line(ack, slots, offer, cfg, llm, echo) if ack else ""
    if lead is None:
        logger.warning("dropped ack for: %s", ack)
        lead = ""
    return f"{lead} {text}".strip()
