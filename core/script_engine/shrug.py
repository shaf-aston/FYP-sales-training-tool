"""Did the reply say anything? A shrug ("dunno man") is never kept as an answer; unclear words about the
question ("I want to make money online") get asked about: "What do you mean by ...?"."""

from core.script_engine.method import ANY
from core.utils import tokenize


class Shrugs:
    def __init__(self, cfg, sense, listener, fill):
        """`fill(template, slots)`: the Filler's, to say their words back; None when they can't be."""
        self._filler = frozenset(cfg["stop_words"]) | frozenset(cfg["filler_words"])
        self._plain = self._filler | frozenset(cfg["vague_words"])  # words that carry no answer
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
        if words <= self._plain:
            return True  # "dunno man": only shrug words, nothing the catch-all should keep
        if not self._sense.unclear:
            return False
        found = self._listener.match(text, {"unclear": list(self._sense.unclear)}, by_clause=False)
        return found.score >= self._sense.unclear_min_score

    def ask_meaning(self, text, question, empty, heard_ahead, known=()):
        """"What do you mean by stuff?": their own words asked about. Only for a shrug, or a miss that is about
        the question ("money online" to "...making money online?"), never off-topic words ("hey"). "" when
        nothing can be asked: only shrug words, an early answer to a later step ("5k a month" is clear), words
        that can't be said back, or an answer they already gave (`known`: "more money" again, after "What
        are you hoping to achieve with more money?"): what they meant is known, so the step is asked another
        way instead. Whether it was already said is the engine's to check."""
        words = set(tokenize(text))
        said = words - self._plain
        repeated = any(said <= set(tokenize(k)) for k in known if k)
        if (not self._sense.ask_meaning or heard_ahead or not said or repeated
                or not (empty or said & set(tokenize(question)))):
            return ""
        return self._fill(self._sense.ask_meaning, {"said": text}) or ""
