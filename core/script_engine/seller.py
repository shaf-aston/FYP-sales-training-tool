"""One selling turn: the script picks the line, the AI only fills small checked gaps."""

import json
import logging
import re
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from core.loader import load_yaml
from core.script_engine.ai_gate import AiGate
from core.script_engine.ai_line import checked_line
from core.script_engine.checks import CheckContext, clip, figures
from core.utils import is_question, tokenize
from core.script_engine.embedder import make_embedder
from core.script_engine.engine import (
    advance, ask_again, asked_line, hear_ahead, jump, move_on, object_to, park, price_open, ready_open, start,
)
from core.script_engine.fill import Filler
from core.script_engine.judge import VAGUE, judge
from core.script_engine.method import ANY, load_common_sense, load_method, load_offer
from core.script_engine.recognise import Listener

ROOT = Path(__file__).resolve().parent.parent.parent
uncovered_log = logging.getLogger("script_engine.uncovered")


def selling_config():
    return load_yaml("selling.yaml")


@lru_cache(maxsize=1)
def shared_embedder():
    """One model per process: loading it is the slow part."""
    return make_embedder(selling_config(), ROOT)


@lru_cache(maxsize=1)
def shared_gate():
    """One AI gate per process: its failure breaker is shared by every call on purpose."""
    return AiGate(selling_config())


def resolve_product(product):
    """The product to sell: the one asked for if it is scripted, else the default."""
    cfg = selling_config()
    return product if product in cfg["products"] else cfg["default_product"]


def build_seller(router, product, embedder=None, gate=None):
    cfg = selling_config()
    entry = cfg["products"][product]
    return ScriptSeller(
        cfg, load_method(entry.get("method", cfg["method"])), load_offer(entry["offer"]), load_common_sense(),
        embedder or shared_embedder(), (gate or shared_gate()).llm(router),
    )


def _answer_labels(step):
    """The step's labelled answers: {signal: [example, ...]}; empty when any reply is its answer."""
    return {r.signal: list(r.examples) for r in step.listen if r.examples}


class ScriptSeller:
    def __init__(self, cfg, method, offer, sense, embedder, llm):
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._listener, self._llm = Listener(cfg, embedder), llm
        self._ai_ok = True
        self._waiting = False  # last reply was a `wait` reply: they stepped away
        self._filler = Filler(cfg, offer, self._ask, frozenset(s.capture for s in method.steps.values() if s.echo))
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
        rest = self._unnudged(text)
        if rest is not None and not tokenize(rest):
            return self._carry_on(self.sense.nudge, step, rephrase=False)  # "ok, what's next?": no answer
        text = text if rest is None else rest  # "credit, what's next?", "yeah, so what's next": the rest answers
        empty = not waiting and not self.state.play and self._says_nothing(text)
        if empty:  # listened to as an answer only: never an interruption, objection or question
            move = self._listen(text, step, empty=True)
            self.state = move.state
            return self._render(move), move.ui_stage
        if not self._is_question(text):  # "do I need 5k a month to start?" is not their goal
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
            lead = self._filler.fill(answer, {})
            return self._then_ask(lead), step.ui_stage
        if self.state.play:
            # they answered the objection play's question: normalise, then ask the step again
            objection = self.method.objections[self.state.play]
            self.state = replace(self.state, play="")
            return self._then_ask(objection.normalise), step.ui_stage
        asking = self._is_question(text)
        if asking and not self._answers(text, step):
            answer = self._answer_uncovered(text, opened) or self.cfg["uncovered_fallback"]
            return self._then_ask(answer, bring_back=True), step.ui_stage

        move = self._listen(text, step)
        if self._hesitates(move):
            return self._revisit(), step.ui_stage
        earlier = {k: v for k, v in self.state.slots.items() if k != step.capture}
        self.state = move.state
        # an answer with a question in it: the question gets an answer when the facts have one, else
        # nothing ("what's next?" needs none). After the judge: a failed AI line can't cost it.
        heard = self._answer_uncovered(text, opened) if asking else ""
        if not heard and not move.ack:
            heard = self._acknowledge(text, step, opened, earlier)
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
        return self._carry_on(said.reply, step, rephrase=said.after == "rephrase")

    def _carry_on(self, lead, step, rephrase):
        """`lead`, then the step in other words; a step with no other words moves on instead (without
        taking the reply as its answer), so the same line is never said twice in a row."""
        if rephrase or step.probes:
            move = ask_again(self.method, replace(self.state, play=""))  # the step's question, not the play's
        else:
            move = move_on(self.method, self.state)
        text, stage = self._go(move)
        return f"{lead} {text}", stage

    def _unnudged(self, text):
        """The reply without a nudge on its end ("credit, what's next?" -> "credit"); None when it has none."""
        for phrase in sorted(self.sense.nudges, key=len, reverse=True):
            words = r"\W+".join(map(re.escape, tokenize(phrase)))
            found = re.search(rf"(?:^|\W)(?:so\W+|ok\W+|okay\W+)?{words}\W*$", text, re.IGNORECASE)
            if found:
                return text[:found.start()].rstrip(" ,;:-")
        return None

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

    def _interrupt(self, text, step, opened, waiting):
        """An everyday interruption, product question or objection - only when it clearly beats
        reading the reply as an answer to the step's own question, like a human closer would."""
        senses = {k: i for k, i in self.sense.interruptions.items() if waiting or not i.after_wait}
        labels = {f"sense:{k}": i.examples for k, i in senses.items()}
        floors = {f"sense:{k}": i.min_score for k, i in senses.items()}  # lowest score a label counts at
        asking = self._is_question(text)
        if asking:
            labels.update({f"fact:{k}": f.examples for k, f in self.offer.facts.items()})
        answers = _answer_labels(step)
        objections = self.method.objections.items()
        if not opened and step.doubts_answer:
            objections = ()  # "money's tight" answers "what holds you back"
        elif not opened and asking:
            objections = [(k, o) for k, o in objections if o.early]  # "is this a scam?" gets an honest early line
        labels.update({f"objection:{k}": o.examples for k, o in objections})
        if ready_open(self.method, self.state.step):
            labels["ready:buyer"] = self.method.ready.examples
            floors["ready:buyer"] = self.method.ready.min_score
        won = self._listener.interruption(text, labels, answers, any(r.signal == ANY for r in step.listen), asking, floors)
        return tuple(won.split(":", 1)) if won else (None, None)

    def _answers(self, text, step):
        """The reply matches one of the step's own answers, even with a question in it ("yeah makes
        sense, what's next?" at the temp check). Two answers too close to call are judged as usual."""
        labels = _answer_labels(step)
        return bool(labels) and self._listener.match(text, labels).label is not None

    def _listen(self, text, step, empty=False):
        labels = _answer_labels(step)
        signal = None
        if labels:
            found = self._listener.match(text, labels)
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
        prompt = c["prompts"]["ack"].format(
            question=step.say_plain or step.say, reply=reply, max_words=c["ack_max_words"],
            memory=c["prompts"]["ack_memory"].format(told=told) if told else "",
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
        It may say anything the facts support, never a new number, promise or price: always checked and
        logged. None when the facts don't cover it (the caller decides whether to say the fallback)."""
        c, offer = self.cfg, self.offer
        if not offer.about:
            return None
        facts = self._filler.fill(offer.about, {})
        if opened and offer.about_after_price:
            facts += " " + self._filler.fill(offer.about_after_price, {})
        told = self._told(self.state.slots)
        prompt = c["prompts"]["answer"].format(
            facts=facts, question=question,
            memory=c["prompts"]["answer_memory"].format(told=told) if told else "",
        )
        fact_words = frozenset(tokenize(facts))
        ctx = CheckContext(
            c["max_words"], 0, opened, offer.price,
            known_figures=frozenset(figures(facts)),  # their own figures are not ours to repeat back as results
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
        return answer

    def _then_ask(self, lead, bring_back=False):
        """`lead`, then (after an interruption or a made-up answer) a bring-back to their last point, then the
        current question again."""
        say, say_plain = asked_line(self.method, self.state)  # the words last used, not always the first
        question = self._filler.render(say, "", say_plain, self.state.slots)
        back = ""
        if bring_back and self.state.last_point:
            back = self._filler.fill(self.sense.bring_back, {"last_point": self.state.last_point}) or ""
        if back and not re.match(r"I( |')", question):
            question = question[:1].lower() + question[1:]
        return " ".join(part.strip() for part in (lead, back, question) if part)

    def _render(self, move, heard=""):
        said = [heard] if heard else []
        for step_id in move.lead:
            lead = self.method.steps[step_id]
            said.append(self._filler.render(lead.say, "", lead.say_plain, move.state.slots))
        step = self.method.steps[move.state.step]
        said.append(self._filler.render(move.say, move.ack, step.say_plain, move.state.slots))
        return " ".join(said)
