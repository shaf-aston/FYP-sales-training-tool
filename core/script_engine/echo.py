"""The echo budget: how much of their own words a reply says back.

Someone who says your words back every time sounds like a mirror; someone who never does sounds like they
weren't listening. So, in this order:
  1. their exact words at the script's moments only (a step marked `moment`, like the goal question);
  2. otherwise one short term of theirs at most (`echo_term_words`), never in two messages in a row, the
     same phrase at most `echo_repeats` times a call, and one quote per message;
  3. or a prewritten line for what they meant (config/script/meanings.yaml), picked by the local matcher;
  4. or nothing back, just the next question.
No AI decides any of it: the same call always gets the same lines."""

from dataclasses import dataclass, replace

from core.utils import tokenize


@dataclass
class Turn:
    """One message being put together."""
    quoted_before: bool     # the message before this one said their words back
    quoted: bool = False    # this one does
    phrases: tuple = ()     # their phrases this one says back
    meant: tuple = ()       # meaning lines this one says
    reply: str = ""         # what they just said


class Echo:
    def __init__(self, cfg, meanings, listener):
        self.cfg, self.meanings, self._listener = cfg, meanings, listener
        self._plain = frozenset(cfg["stop_words"]) | frozenset(cfg["filler_words"]) | frozenset(cfg["vague_words"])
        self._labels = {k: list(m.examples) for k, m in meanings.items.items()}

    def examples(self):
        return [e for items in self._labels.values() for e in items]

    @staticmethod
    def new_turn(state, reply=""):
        return Turn(quoted_before=state.quoted, reply=reply)

    def may_quote(self, turn, state, phrases, moment):
        """May this message say these phrases of theirs back? `phrases` empty = a line that may say their
        words but names none (an AI "I heard you" line)."""
        if turn.quoted:
            return False  # one quote per message
        if moment:
            return True
        if turn.quoted_before:
            return False
        if any(len(p.split()) > self.cfg["echo_term_words"] for p in phrases):
            return False  # a whole sentence of theirs waits for a moment
        used = list(state.echoed) + list(turn.phrases)
        return all(used.count(p.lower()) < self.cfg["echo_repeats"] for p in phrases)

    @staticmethod
    def said(turn, phrases):
        turn.quoted = True
        turn.phrases += tuple(p.lower() for p in phrases)

    def quoted(self, line, reply):
        """Their words that carry meaning which `line` says back, in their order."""
        said = set(tokenize(line))
        return [w for w in dict.fromkeys(tokenize(reply)) if w not in self._plain and w in said]

    def quotes(self, line, reply):
        """True when `line` says their reply back: most of its words that carry meaning, or two of them."""
        theirs = set(tokenize(reply)) - self._plain
        return bool(theirs) and len(self.quoted(line, reply)) >= min(2, len(theirs))

    def count(self, turn, line):
        """A line already in words ("What do you mean by wanting to make money online?", an AI probe) that
        says their reply back is a quote too: counted, so the next message doesn't quote again."""
        if line and not turn.quoted and self.quotes(line, turn.reply):
            self.said(turn, (" ".join(self.quoted(line, turn.reply)),))

    def meaning(self, reply, state, turn):
        """The next unsaid line for what the reply means, or "" when it means none (or they were all said)."""
        if not self._labels or len(set(tokenize(reply)) - self._plain) < self.meanings.min_words:
            return ""  # too few words to mean anything this deep: "debt", "for my mum"
        found = self._listener.match(reply, self._labels)
        if found.score < self.meanings.min_score:
            return ""
        best = found.candidates[0]
        said = set(state.meant) | set(turn.meant)
        return next((line for line in self.meanings.items[best].lines if line not in said), "")

    @staticmethod
    def settle(state, turn):
        """The call state with this message's echoes counted."""
        return replace(state, quoted=turn.quoted, echoed=state.echoed + turn.phrases, meant=state.meant + turn.meant)
