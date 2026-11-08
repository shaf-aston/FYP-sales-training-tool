"""Did the reply say anything? A shrug ("dunno man") is never kept as an answer; unclear words about the
question ("I want to make money online") get asked about: "What do you mean by ...?"."""

import re

from core.buy_mode.script_engine.config import plain_words
from core.buy_mode.script_engine.method import ANY
from core.infra.utils import tokenize


class Shrugs:
    def __init__(self, cfg, sense, listener, fill):
        """`fill(template, slots)`: the Filler's, to say their words back; None when they can't be."""
        self._fillers = frozenset(cfg["filler_words"])
        stop = frozenset(cfg["stop_words"]) - frozenset(cfg["side_words"])  # "I'm in" takes a side: never a shrug
        self._filler = stop | self._fillers
        self._blank = stop | frozenset(cfg["no_answer_words"])
        self._no = stop | frozenset(cfg["no_words"])
        self._polite = frozenset(cfg["no_polite_words"])
        self._plain = plain_words(cfg)
        self._phrases = [tokenize(p) for p in cfg["shrug_phrases"]]
        # round 66: a reply of only tags ("hand on heart", "in all honesty") says nothing too; the say-back below
        # keeps them, as "like" is one and "things like money" needs it
        tags = dict.fromkeys([*cfg["filler_tags"], *cfg["end_tags"], *cfg["filler_leads"]])
        self._cuts = [*self._phrases, *map(tokenize, tags)]
        longest = sorted(self._phrases, key=len, reverse=True)
        self._phrase_cut = re.compile(r"\b(?:" + "|".join(r"\W+".join(map(re.escape, p)) for p in longest) + r")\b[\s,.;:!-]*", re.IGNORECASE)
        self._asks = set(cfg["question_words"])  # "what" shares no topic with a question: "what I said" is not about it
        self._sense, self._listener, self._fill = sense, listener, fill

    def says_nothing(self, text, step, asking):
        """"ok", "idk", "dunno man", "stuff I guess": no answer to an open question. Beyond the filler words,
        only on a step whose catch-all route would keep it as the answer (a step with no catch-all hears these
        with its own labels), and a question is never a shrug."""
        words = set(tokenize(text))
        if words <= self._filler:  # also no words at all: "👍", "..."
            return True
        if not any(r.label == ANY for r in step.listen) or asking:
            return False
        if self._words(text) <= self._plain:
            return True  # "dunno man", "we'll see": only shrug words, nothing the catch-all should keep
        return self.hedges(text)

    def _words(self, text):
        """The reply's words, less any shrug phrase or tag in it ("who knows", "hard to say", "per se"): those say
        nothing."""
        words = tokenize(text)
        for phrase in self._cuts:
            n = len(phrase)
            words = [w for j, w in enumerate(words)
                     if not any(words[k:k + n] == phrase for k in range(max(0, j - n + 1), j + 1))]
        return set(words)

    def filler(self, text):
        """Only filler words ("ok", "yeah", "right"): with a rise ("ok?") it asks nothing."""
        words = set(tokenize(text))
        return bool(words) and words <= self._fillers

    def plain_no(self, text, polite=False):
        """Only a no ("nah", "nope"): an answer, never "what do you mean?" or a worry. `polite`: thanks with it
        too ("no thank you"), said to a yes-or-no question; to an open one that is no to the call."""
        words = set(tokenize(text)) - (self._polite if polite else set())
        return bool(words - self._filler) and words <= self._no

    def blank(self, text):
        """Only words that answer nothing, not even a yes-or-no question ("lol", "hmm", "idk"). No words at
        all ("👍") is not blank: a thumbs-up can say yes."""
        words = set(tokenize(text))
        return bool(words) and words <= self._blank

    def hedges(self, text):
        """One part of a reply that says nothing on its own ("I don't know", "honestly", "lol idk"): reply.py
        leaves it out of what they meant, so "I don't know, enough to live" answers "enough to live"."""
        return self.unsure(text) >= self._sense.unclear_min_score

    def unsure(self, text):
        """How close the reply is to not knowing ("let me think" 1.0); 0 with nothing to match."""
        if not self._sense.unclear or not tokenize(text):  # by meaning only: "yes" and "I'm in" are plain words that answer
            return 0.0
        return self._listener.match(text, {"unclear": list(self._sense.unclear)}, by_clause=False).score

    def ask_meaning(self, text, question, empty, heard_ahead, known=()):
        """"What do you mean by stuff?": their own words asked about. Only for a shrug, or a miss that is about
        the question ("money online" to "...making money online?"), never off-topic words ("hey"). "" when
        nothing can be asked: only shrug words, an early answer to a later step ("5k a month" is clear), words
        that can't be said back, or an answer they already gave (`known`: "more money" again, after "What
        are you hoping to achieve with more money?"): what they meant is known, so the step is asked another
        way instead. Whether it was already said is the engine's to check."""
        said = self._words(text) - self._plain
        repeated = any(said <= set(tokenize(k)) for k in known if k)
        if (not self._sense.ask_meaning or heard_ahead or not said or repeated
                or not (empty or said & set(tokenize(question)) - self._asks)):
            return ""
        back = self._phrase_cut.sub("", text).strip(" ,.;:!-") or text  # "who knows, stuff": "What do you mean by stuff?"
        return self._fill(self._sense.ask_meaning, {"said": back}) or ""
