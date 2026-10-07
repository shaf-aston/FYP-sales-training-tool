"""One selling turn: the script picks the line, the AI only fills small checked gaps."""

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import cache, lru_cache
from pathlib import Path

from core.loader import load_yaml
from core.script_engine.ai_line import checked_line
from core.script_engine.checks import NUMBER, CheckContext, clip
from core.utils import is_question, tokenize
from core.script_engine.embedder import make_embedder
from core.script_engine.engine import (
    advance, ask_again, asked_line, hear_ahead, jump, move_on, object_to, park, price_open, ready_open, start,
)
from core.script_engine.fill import fill_line, fill_step
from core.script_engine.judge import VAGUE, judge
from core.script_engine.method import ANY, load_common_sense, load_method, load_offer
from core.script_engine.recognise import recognise

ROOT = Path(__file__).resolve().parent.parent.parent
uncovered_log = logging.getLogger("script_engine.uncovered")


class _Breaker:
    """Shared by every call: one rate limit covers the whole server. Opens after `limit` failures
    in a row, so one slow call doesn't silence the AI for every user."""

    def __init__(self):
        self._lock = threading.Lock()
        self.fails = 0
        self.resting_until = 0.0

    def resting(self):
        with self._lock:
            return time.monotonic() < self.resting_until

    def failed(self, limit, rest_seconds):
        with self._lock:
            self.fails += 1
            if self.fails >= limit:
                self.fails = 0
                self.resting_until = time.monotonic() + rest_seconds

    def worked(self):
        with self._lock:
            self.fails = 0


_breaker = _Breaker()


@cache
def _pool(workers):
    return ThreadPoolExecutor(max_workers=workers, thread_name_prefix="script-ai")


def make_llm(router, timeout, rest_seconds, fail_limit, workers):
    """Adapt the provider router to llm(prompt, max_tokens) -> text. Raises on failure or timeout.
    After `fail_limit` failures in a row the AI is left alone for `rest_seconds`, so no turn waits on
    a dead provider."""

    def call(prompt, max_tokens):
        result = router.chat_with_fallback(
            [{"role": "user", "content": prompt}], max_tokens=max_tokens
        )
        if not result.ok:
            raise RuntimeError(result.response.error or "provider failed")
        return result.response.content

    def guarded(prompt, max_tokens):
        if _breaker.resting():
            raise RuntimeError("AI resting after repeated failures")
        try:
            text = _pool(workers).submit(call, prompt, max_tokens).result(timeout)
        except Exception:
            _breaker.failed(fail_limit, rest_seconds)
            raise
        _breaker.worked()
        return text

    return guarded


def selling_config():
    return load_yaml("selling.yaml")


@lru_cache(maxsize=1)
def shared_embedder():
    """One model per process: loading it is the slow part."""
    return make_embedder(selling_config(), ROOT)


def build_seller(router, product, embedder=None):
    cfg = selling_config()
    entry = cfg["products"][product]
    return ScriptSeller(
        cfg, load_method(entry.get("method", cfg["method"])), load_offer(entry["offer"]), load_common_sense(),
        embedder or shared_embedder(),
        make_llm(router, cfg["ai_timeout_seconds"], cfg["ai_rest_seconds"], cfg["ai_fail_limit"], cfg["ai_workers"]),
    )


class ScriptSeller:
    def __init__(self, cfg, method, offer, sense, embedder, llm):
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._embedder, self._llm = embedder, llm
        self._ai_ok = True
        self._waiting = False  # last reply was a `wait` reply: they stepped away
        self._said = {}  # filled lines: the same line with the same answers is said the same way
        self._opening = start(method)
        self.state = self._opening.state
        embedder.warm(self._script_examples())

    def _script_examples(self):
        found = [e for i in self.sense.interruptions.values() for e in i.examples]
        found += [e for f in self.offer.facts.values() for e in f.examples]
        found += [e for o in self.method.objections.values() for e in o.examples]
        found += [e for s in self.method.steps.values() for r in s.listen for e in r.examples]
        found += list(self.method.ready.examples) if self.method.ready else []
        return found

    def reset(self, state=None):
        self.state = state or self._opening.state

    def opening(self):
        """The first line of the call: (text, ui_stage)."""
        self._ai_ok = True
        return self._render(self._opening), self._opening.ui_stage

    def _ask(self, prompt, max_tokens):
        """The only door to the AI. After one failure it stays shut for the rest of the turn."""
        if not self._ai_ok:
            raise RuntimeError("AI skipped: it already failed this turn")
        try:
            return self._llm(prompt, max_tokens)
        except Exception:
            self._ai_ok = False
            raise

    # ---- one turn -------------------------------------------------------------------------

    def reply(self, text):
        """Answer one prospect message. Returns (text, ui_stage)."""
        self._ai_ok = True
        waiting, self._waiting = self._waiting, False
        step = self.method.steps[self.state.step]
        opened = price_open(self.method, self.state.step)
        empty = not waiting and not self.state.play and self._says_nothing(text)
        if empty:  # listened to as an answer only: never an interruption, objection or question
            move = self._listen(text, step, empty=True)
            self.state = move.state
            return self._render(move), move.ui_stage
        self.state = hear_ahead(self.method, self.state, text)  # kept whatever else the reply turns out to be
        kind, name = self._interrupt(text, step, opened, waiting)

        if kind == "ready":
            return self._go(jump(self.method, self.state, self.method.ready.then))
        if kind == "sense":
            return self._sense(self.sense.interruptions[name], step)
        if kind == "objection" and not opened:
            self.state = park(self.state, name)
            return self._then_ask(self.method.objections[name].early or self.sense.park), step.ui_stage
        if kind == "objection":
            return self._go(object_to(self.method, self.state, name, self.cfg["objection_loops"]))
        if kind == "fact":
            f = self.offer.facts[name]
            answer = f.late_answer if opened and f.late_answer else f.answer
            lead = fill_line(answer, {}, self.offer, self.cfg, self._ask)
            return self._then_ask(lead), step.ui_stage
        if self.state.play:
            # they answered the objection play's question: normalise, then ask the step again
            objection = self.method.objections[self.state.play]
            self.state = replace(self.state, play="")
            return self._then_ask(objection.normalise), step.ui_stage
        if self._is_question(text):
            return self._then_ask(self._answer_uncovered(text, opened), bring_back=True), step.ui_stage

        move = self._listen(text, step)
        if self._hesitates(move):
            return self._revisit(), step.ui_stage
        earlier = {k: v for k, v in self.state.slots.items() if k != step.capture}
        self.state = move.state
        # after the judge: a failed ack can't cost it
        heard = "" if move.ack else self._acknowledge(text, step, opened, earlier)
        return self._render(move, heard), move.ui_stage

    def _go(self, move):
        """Take a move as it is: no "I heard you" line in front of it."""
        self.state = move.state
        return self._render(move), move.ui_stage

    def _sense(self, said, step):
        """An everyday interruption: its reply, then what its `after` says."""
        if said.after == "wait":
            self._waiting = True
            return said.reply, step.ui_stage
        if said.after == "ask":
            return self._then_ask(said.reply, bring_back=True), step.ui_stage
        if said.after == "rephrase" or step.probes:
            move = ask_again(self.method, self.state)
        else:  # rephrase_else_move_on on a step with no other words: don't say the same line again
            move = move_on(self.method, self.state)
        text, stage = self._go(move)
        return f"{said.reply} {text}", stage

    def _hesitates(self, move):
        """They held back at the revisit step while a worry from earlier is still unanswered."""
        step_id = self.method.revisit_step
        return (self.state.step == step_id and move.state.step == step_id
                and bool(self.state.parked) and not self.state.play)

    def _revisit(self):
        """Raise the oldest parked worry now: it is likely what holds them back."""
        move = object_to(self.method, self.state, self.state.parked[0], self.cfg["objection_loops"])
        self.state = move.state
        line = self._render(move)
        return f"{self.sense.revisit} {line[:1].lower()}{line[1:]}"

    def ui_stage(self):
        """The UI stage of the step the call is on."""
        return self.method.steps[self.state.step].ui_stage

    def training(self):
        """Notes for the trainee, straight from the script step - no AI, instant."""
        step = self.method.steps[self.state.step]
        title = f"{step.id} {step.name}".strip() if step.name else step.id
        return {
            "what_happened": f"Script step {title}.",
            "next_move": f"Listen for: {step.note}" if step.note else "Listen to their answer.",
            "watch_for": [],
        }

    def _recognise(self, text, labels):
        c = self.cfg
        return recognise(text, labels, self._embedder, c["threshold"], c["margin"],
                         c["close_call_k"], c["near_miss"])

    def _interrupt(self, text, step, opened, waiting):
        """An everyday interruption, product question or objection - only when it clearly beats
        reading the reply as an answer to the step's own question, like a human closer would."""
        labels = {f"sense:{k}": i.examples for k, i in self.sense.interruptions.items()
                  if waiting or not i.after_wait}
        asking = self._is_question(text)
        if asking:
            labels.update({f"fact:{k}": f.examples for k, f in self.offer.facts.items()})
        answers = {r.signal: list(r.examples) for r in step.listen if r.examples}
        objections = self.method.objections.items()
        if not opened and step.doubts_answer:
            objections = ()  # "money's tight" answers "what holds you back"
        elif not opened and asking:
            objections = [(k, o) for k, o in objections if o.early]  # "is this a scam?" gets an honest early line
        labels.update({f"objection:{k}": o.examples for k, o in objections})
        if ready_open(self.method, self.state.step):
            labels["ready:buyer"] = self.method.ready.examples
        found = self._recognise(text, labels)
        if not found.label or found.close:
            return None, None
        kind, name = found.label.split(":", 1)
        if kind == "fact":
            return kind, name  # a product question is never an answer
        bar = 0.0 if answers else self.cfg["interrupt_threshold"]
        if answers:
            as_answer = self._recognise(text, answers)
            bar = as_answer.score if as_answer.label else 0.0  # only a real answer competes
        if any(r.signal == ANY for r in step.listen):
            bar = max(bar, self.cfg["interrupt_threshold"])  # any reply is an answer: interrupt only when sure
        bar = max(bar, self._floor(kind, name))
        return (kind, name) if found.score > bar else (None, None)

    def _floor(self, kind, name):
        """The lowest score a label counts at on any step (0 = no floor of its own)."""
        if kind == "ready":
            return self.method.ready.min_score
        if kind == "sense":
            return self.sense.interruptions[name].min_score
        return 0.0

    def _listen(self, text, step, empty=False):
        labels = {r.signal: list(r.examples) for r in step.listen if r.examples}
        signal = None
        if labels:
            found = self._recognise(text, labels)
            signal = found.label
            if found.close:
                pick = judge(text, {c: labels[c] for c in found.candidates}, self._ask,
                             self.cfg["judge_tokens"])
                signal = None if pick == VAGUE else pick
        return advance(self.method, self.state, signal, text, empty)

    def _says_nothing(self, text):
        """"ok", "sure", "yeah": no answer to an open question, and no interruption either."""
        words = set(tokenize(text))
        return bool(words) and words <= set(self.cfg["stop_words"]) | set(self.cfg["filler_words"])

    def _told(self, slots):
        """Their earlier answers, one per line and cut short, for an AI prompt."""
        return "\n".join(f"- {clip(v, self.cfg['memory_chars'])}" for v in slots.values() if v)

    def _acknowledge(self, reply, step, opened, earlier):
        """One short checked sentence showing their answer was heard, in their own words; it may link to
        something they said earlier. Nothing when it fails: honest silence beats a canned line."""
        c = self.cfg
        if not c["ack"]:
            return ""
        told = self._told(earlier)
        memory = (
            f"Earlier they told you:\n<earlier>\n{told}\n</earlier>\n"
            "If it fits naturally, link their answer to something they told you earlier.\n"
        ) if told else ""
        prompt = (
            "You are the salesperson on a call. You asked:\n"
            f"<question>{step.say_plain or step.say}</question>\n"
            f"They answered: <reply>{reply}</reply>\n"
            f"{memory}"
            f"Write one short sentence (at most {c['ack_max_words']} words) that shows you heard them, "
            "using their own words and speaking to them as 'you'. No question, no advice, no praise. "
            "Answer with the sentence only."
        )
        ctx = CheckContext(
            c["ack_max_words"], 0, opened, self.offer.price,
            prospect_words=frozenset(tokenize(reply)) | frozenset(tokenize(told)),
            stop_words=frozenset(c["stop_words"]) | frozenset(c["ack_words"]),
        )
        return checked_line(self._ask, prompt, c["ack_tokens"], ctx, c, "ack", retries=c["ack_retries"]) or ""

    def _is_question(self, text):
        return is_question(text, self.cfg["question_starts"], self.cfg["filler_tags"])

    def _answer_uncovered(self, question, opened):
        """A short answer to a product question nothing covers, from the offer's facts and what they told us.
        It may say anything the facts support, never a new number, promise or price: always checked,
        always logged, and the honest fallback when the facts don't cover it."""
        c, offer = self.cfg, self.offer
        facts = f"{offer.about} A {offer.months}-month programme. Pillars: {', '.join(offer.pillars)}.".strip()
        if opened:
            facts += f" The investment is {offer.price}."
        told = self._told(self.state.slots)
        memory = f"What they told you earlier:\n<earlier>\n{told}\n</earlier>\n" if told else ""
        prompt = (
            f"You are the salesperson on a call. Programme facts:\n<facts>{facts}</facts>\n"
            f"{memory}"
            "A prospect asked the question below.\n"
            f"<question>{question}</question>\n"
            "Answer in one or two short sentences: warm, confident and helpful toward yes, linked to what "
            "they told you when it fits. Say only what the facts support. Never invent numbers, results, "
            "timeframes, promises, prices or links. Do not ask a question. "
            "If the facts don't answer it, reply with NOT_COVERED only."
        )
        fact_words = frozenset(tokenize(facts))
        ctx = CheckContext(
            c["max_words"], 0, opened, offer.price,
            known_numbers=frozenset(NUMBER.findall(facts)),  # their own figures are not ours to repeat back as results
            banned=frozenset(c["answer_banned_words"]) - fact_words,
        )

        def clean(raw):
            return None if "not_covered" in raw.lower().replace(" ", "_") else raw.strip()

        answer = checked_line(self._ask, prompt, c["answer_tokens"], ctx, c, "product answer", clean)
        if c["log_uncovered"]:
            uncovered_log.info(json.dumps({
                "question": clip(question, c["log_text_chars"]),
                "answer": answer and clip(answer, c["log_text_chars"]),
            }))
        return answer or c["uncovered_fallback"]

    def _then_ask(self, lead, bring_back=False):
        """`lead`, then (after an interruption or a made-up answer) a bring-back to their last point, then the
        current question again."""
        say, say_plain = asked_line(self.method, self.state)  # the words last used, not always the first
        question = self._fill(say, "", say_plain, self.state.slots)
        back = ""
        if bring_back and self.state.last_point:
            back = fill_line(self.sense.bring_back, {"last_point": self.state.last_point},
                             self.offer, self.cfg, self._ask) or ""
        if back and not re.match(r"I( |')", question):
            question = question[:1].lower() + question[1:]
        return " ".join(part.strip() for part in (lead, back, question) if part)

    def _fill(self, say, ack, say_plain, slots):
        key = (say, ack, tuple(sorted(slots.items())))
        if key not in self._said:
            self._said[key] = fill_step(say, ack, say_plain, slots, self.offer, self.cfg, self._ask)
        return self._said[key]

    def _render(self, move, heard=""):
        said = [heard] if heard else []
        for step_id in move.lead:
            lead = self.method.steps[step_id]
            said.append(self._fill(lead.say, "", lead.say_plain, move.state.slots))
        step = self.method.steps[move.state.step]
        said.append(self._fill(move.say, move.ack, step.say_plain, move.state.slots))
        return " ".join(said)
