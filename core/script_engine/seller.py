"""One selling turn: the script picks the line, the AI only fills small checked gaps."""

import json
import logging
from functools import lru_cache
from pathlib import Path

from core.loader import load_yaml
from core.script_engine.checks import CheckContext, check
from core.script_engine.embedder import make_embedder
from core.script_engine.engine import advance, object_to, price_open, start
from core.script_engine.fill import fill_line, fill_step
from core.script_engine.judge import VAGUE, judge
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.recognise import recognise

ROOT = Path(__file__).resolve().parent.parent.parent
fallback_log = logging.getLogger("script_engine.fallback")
uncovered_log = logging.getLogger("script_engine.uncovered")


def make_llm(router):
    """Adapt the app's provider router to llm(prompt, max_tokens) -> text. Raises on failure."""

    def llm(prompt, max_tokens):
        result = router.chat_with_fallback(
            [{"role": "user", "content": prompt}], max_tokens=max_tokens
        )
        if not result.ok:
            raise RuntimeError(result.response.error or "provider failed")
        return result.response.content

    return llm


@lru_cache(maxsize=1)
def shared_embedder():
    """One model per process: loading it is the slow part."""
    return make_embedder(load_yaml("selling.yaml"), ROOT)


def build_seller(router, embedder=None):
    cfg = load_yaml("selling.yaml")
    return ScriptSeller(
        cfg, load_method(cfg["method"]), load_offer(cfg["offer"]), load_common_sense(),
        embedder or shared_embedder(), make_llm(router),
    )


class ScriptSeller:
    def __init__(self, cfg, method, offer, sense, embedder, llm):
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._embedder, self._llm = embedder, llm
        self._opening = start(method)
        self.state = self._opening.state

    def reset(self, state=None):
        self.state = state or self._opening.state

    def opening(self):
        """The first line of the call: (text, ui_stage)."""
        return self._render(self._opening), self._opening.ui_stage

    def reply(self, text):
        """Answer one prospect message. Returns (text, ui_stage)."""
        return self._turn(text, self._llm)

    def observe(self, text):
        """Move the script as `reply` would, with no AI call and no output (used on replay)."""
        self._turn(text, None)

    # ---- one turn -------------------------------------------------------------------------

    def _turn(self, text, llm):
        step = self.method.steps[self.state.step]
        stage = step.ui_stage
        sense = self._match(text, {k: i.examples for k, i in self.sense.interruptions.items()})
        if sense:
            return self._then_ask(self.sense.interruptions[sense].reply, llm), stage

        opened = price_open(self.method, self.state.step)
        if opened:
            objection = self._match(text, {k: o.examples for k, o in self.method.objections.items()})
            if objection:
                move = object_to(self.method, self.state, objection, self.cfg["objection_loops"])
                self.state = move.state
                return move.say, move.ui_stage

        fact = self._match(text, {k: f.examples for k, f in self.offer.facts.items()})
        if fact:
            f = self.offer.facts[fact]
            answer = f.late_answer if opened and f.late_answer else f.answer
            return self._then_ask(fill_line(answer, {}, self.offer, self.cfg, llm), llm), stage

        if self._is_question(text):
            return self._then_ask(self._answer_uncovered(text, opened, llm), llm), stage

        move = self._listen(text, step, llm)
        self.state = move.state
        return (self._render(move, llm) if llm else ""), move.ui_stage

    def _match(self, text, labels):
        """A confident label for `text`, or None (a close call does not count here)."""
        found = recognise(text, labels, self._embedder, self.cfg["threshold"],
                          self.cfg["margin"], self.cfg["close_call_k"])
        return None if found.close else found.label

    def _listen(self, text, step, llm):
        labels = {r.signal: list(r.examples) for r in step.listen if r.examples}
        signal = None
        if labels:
            found = recognise(text, labels, self._embedder, self.cfg["threshold"],
                              self.cfg["margin"], self.cfg["close_call_k"])
            signal = found.label
            if found.close:
                signal = None
                if llm:
                    pick = judge(text, {c: labels[c] for c in found.candidates}, llm)
                    signal = None if pick == VAGUE else pick
        return advance(self.method, self.state, signal, text)

    def _is_question(self, text):
        first = text.strip().lower().split(" ", 1)[0]
        return text.strip().endswith("?") and first in self.cfg["question_starts"]

    def _answer_uncovered(self, question, opened, llm):
        """One least-resistance sentence for a product question nothing covers; logged."""
        answer = None
        if llm:
            facts = f"{self.offer.months}-month programme; pillars: {', '.join(self.offer.pillars)}"
            if opened:
                facts += f"; price {self.offer.price}"
            prompt = (
                f"A prospect asked: {question}\nProgramme facts: {facts}\n"
                "Answer in one short sentence, the way that causes least resistance and helps "
                "move toward yes. Do not ask a question. Do not mention price unless it is in "
                "the facts."
            )
            ctx = CheckContext(self.cfg["max_words"], 0, opened, self.offer.price)
            for _ in range(1 + self.cfg["ai_retries"]):
                try:
                    candidate = llm(prompt, 60).strip()
                except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
                    fallback_log.warning("product answer: AI unavailable: %s", exc)
                    break
                broken = check(candidate, ctx)
                if not broken:
                    answer = candidate
                    break
                fallback_log.warning("product answer %r broke %s", candidate, broken)
            uncovered_log.info(json.dumps({"question": question, "answer": answer}))
        return answer

    def _then_ask(self, lead, llm):
        """`lead` (may be None), then a bring-back, then the current step's question again."""
        step = self.method.steps[self.state.step]
        question = fill_step(step.say, "", step.say_plain, self.state.slots, self.offer,
                             self.cfg, llm) if llm else ""
        back = ""
        if llm and self.state.last_point:
            back = fill_line(self.sense.bring_back, {"last_point": self.state.last_point},
                             self.offer, self.cfg, llm) or ""
            if back and not question.startswith("I"):
                question = question[:1].lower() + question[1:]
        return " ".join(part for part in (lead, back + question) if part) if llm else ""

    def _render(self, move, llm=None):
        step = self.method.steps[move.state.step]
        return fill_step(move.say, move.ack, step.say_plain, move.state.slots, self.offer,
                         self.cfg, llm or self._llm)

