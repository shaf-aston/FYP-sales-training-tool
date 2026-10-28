"""The echo budget: how much of their own words a reply says back.

Someone who says your words back every time sounds like a mirror; someone who never does sounds like they
weren't listening. So, in this order:
  1. their exact words at the script's moments only (a step marked `moment`, like the goal question);
  2. otherwise one short term of theirs at most (`echo_term_words`), never in two messages in a row, the
     same phrase at most `echo_repeats` times a call, and one quote per message;
  3. or a prewritten line for what they meant (meanings.py);
  4. or nothing back, just the next question.
No AI decides any of it: the same call always gets the same lines."""

from dataclasses import dataclass, replace

from core.buy_mode.script_engine.config import plain_words
from core.infra.utils import tokenize


@dataclass
class Turn:
    """One message being put together."""
    reply: str = ""         # what they just said
    phrases: tuple = ()     # their phrases this one says back
    meant: tuple = ()       # meaning lines this one says
    side: bool = False      # a side reply (fact, parked worry) that said the step again


class Echo:
    def __init__(self, cfg):
        self.cfg, self._plain = cfg, plain_words(cfg)

    def may_quote(self, turn, state, phrases, moment):
        """May this message say these phrases of theirs back? `phrases` empty = a line that may say their
        words but names none (an AI "I heard you" line)."""
        if turn.phrases:
            return False  # one quote per message
        if moment:
            return True
        if state.quoted:
            return False  # the message before this one did
        if any(len(p.split()) > self.cfg["echo_term_words"] for p in phrases):
            return False  # a whole sentence of theirs waits for a moment
        keys = [self._key(e) for e in state.echoed]
        return all(keys.count(self._key(p)) < self.cfg["echo_repeats"] for p in phrases)

    def _key(self, phrase):
        """A phrase by the words that carry meaning: "your bills" (a filled blank) and "bills" (an AI line's
        quote) count as one."""
        return tuple(w for w in tokenize(phrase) if w not in self._plain)

    @staticmethod
    def said(turn, phrases):
        turn.phrases += tuple(p.lower() for p in phrases)

    def quoted(self, line, reply):
        """Their words that carry meaning which `line` says back, in their order: [] unless it says most of
        them, or two."""
        theirs = [w for w in dict.fromkeys(tokenize(reply)) if w not in self._plain]
        said = set(tokenize(line))
        words = [w for w in theirs if w in said]
        return words if theirs and len(words) >= min(2, len(theirs)) else []

    def count(self, turn, line):
        """A line already in their words ("What do you mean by wanting to make money online?", an AI probe)
        is a quote too: counted, so the next message doesn't quote again."""
        if line and not turn.phrases and (words := self.quoted(line, turn.reply)):
            self.said(turn, (" ".join(words),))

    @staticmethod
    def settle(state, turn):
        """The call state with this message's echoes counted."""
        return replace(state, quoted=bool(turn.phrases), echoed=state.echoed + turn.phrases, meant=state.meant + turn.meant)
