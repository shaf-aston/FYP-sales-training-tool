"""Every AI call the seller makes, by name: listen, ack, answer, judge. Prompts, checks and the
per-turn breaker live here only, so the seller never builds a prompt and tests can swap in a fake."""

import json
import logging

from core.buy_mode.script_engine.ai.line import checked_line
from core.buy_mode.script_engine.ai.checks import CheckContext, clip, figures
from core.buy_mode.script_engine.ai.judge import judge
from core.buy_mode.script_engine.ai.listen import hear
from core.buy_mode.script_engine.words.tone import plain
from core.infra.utils import tokenize

from core.infra.logs import timed

uncovered_log = logging.getLogger("script_engine.uncovered")


class Voice:
    """The live AI: `llm(prompt, max_tokens)` behind four named calls. After one failure in a turn the
    rest of that turn goes without it (see `new_turn`)."""

    def __init__(self, cfg, offer, llm):
        self.cfg, self.offer, self._llm = cfg, offer, llm
        self._ok = True
        self._plain = frozenset(cfg["stop_words"]) | frozenset(cfg["ack_words"])  # never "their words"
        self._banned = frozenset(cfg["answer_banned_words"])
        self._banned_phrases = tuple(cfg["banned_phrases"])

    def new_turn(self):
        self._ok = True

    @timed
    def _ask(self, prompt, max_tokens):
        """The only door to the AI. After one failure it stays shut for the rest of the turn."""
        if not self._ok:
            raise RuntimeError("AI skipped: it already failed this turn")
        try:
            return self._llm(prompt, max_tokens)
        except Exception:
            self._ok = False
            raise

    def _told(self, slots):
        """Their earlier answers, one per line and cut short, for a prompt."""
        return "\n".join(f"- {clip(v, self.cfg['memory_chars'])}" for v in slots.values() if v)

    def _ack_ctx(self, reply, told, opened):
        c = self.cfg
        return CheckContext(
            c["ack_max_words"], 0, opened, self.offer.price,
            prospect_words=frozenset(tokenize(reply)) | frozenset(tokenize(told)),
            stop_words=self._plain, banned_phrases=self._banned_phrases,
        )

    @timed
    def listen(self, reply, concept, question, earlier, opened):
        """Did they give the step's `concept`? A `Heard` (an ack if so, a probe if not), or None when the
        AI failed or answered off-format: the rest of the turn then goes without it."""
        c = self.cfg
        told = self._told(earlier)
        question = plain(question)  # the AI reads words, not tone marks
        prompt = c["prompts"]["listen"].format(
            concept=concept, question=question, reply=reply,
            max_words=c["ack_max_words"], probe_words=c["probe_max_words"],
            memory=c["prompts"]["ack_memory"].format(told=told) if told else "",
        )
        ack_ctx = self._ack_ctx(reply, told, opened)
        probe_ctx = CheckContext(
            c["probe_max_words"], 1, opened, self.offer.price,
            known_figures=frozenset(figures(reply + " " + told)), banned_phrases=self._banned_phrases,
            banned=self._banned - ack_ctx.prospect_words,  # a probe promises nothing
        )
        heard = hear(self._ask, prompt, c["listen_tokens"], ack_ctx, probe_ctx, question, c)
        if heard is None:
            self._ok = False  # off-format counts as a failure: no second call (an ack) this turn
        return heard

    @timed
    def ack(self, reply, question, earlier, opened):
        """One short checked sentence showing their answer was heard, in their own words; it may link to
        something they said earlier. "" when it fails: honest silence beats a canned line."""
        c = self.cfg
        if not c["ack"]:
            return ""
        told = self._told(earlier)
        prompt = c["prompts"]["ack"].format(
            question=plain(question), reply=reply, max_words=c["ack_max_words"],
            memory=c["prompts"]["ack_memory"].format(told=told) if told else "",
        )
        ctx = self._ack_ctx(reply, told, opened)
        return checked_line(self._ask, prompt, c["ack_tokens"], ctx, c, "ack", retries=c["ack_retries"]) or ""

    @timed
    def answer(self, question, facts, slots, opened):
        """A short answer to a product question from the offer's `facts` and what they told us. It may say
        anything the facts support, never a new number, promise or price: always checked and logged.
        None when the facts don't cover it."""
        c = self.cfg
        told = self._told(slots)
        prompt = c["prompts"]["answer"].format(
            facts=facts, question=question,
            memory=c["prompts"]["answer_memory"].format(told=told) if told else "",
        )
        ctx = CheckContext(
            c["max_words"], 0, opened, self.offer.price,
            known_figures=frozenset(figures(facts)),  # their own figures are not ours to repeat back as results
            banned=self._banned - frozenset(tokenize(facts)), banned_phrases=self._banned_phrases,
        )

        def clean(raw):
            return None if "not_covered" in raw.lower().replace(" ", "_") else raw.strip()

        said = checked_line(self._ask, prompt, c["answer_tokens"], ctx, c, "product answer", clean)
        if c["log_uncovered"]:
            uncovered_log.info(json.dumps({
                "question": clip(question, c["log_text_chars"]),
                "answer": said and clip(said, c["log_text_chars"]),
            }))
        return said

    def judge(self, reply, candidates):
        """Which of `candidates` ({label: [examples]}) the reply means, or VAGUE."""
        return judge(reply, candidates, self._ask, self.cfg)
