"""What one prospect reply was heard as, before anything is said back: one `Verdict` per turn."""

import re
from dataclasses import dataclass

from core.buy_mode.script_engine.engine import asked_line, question_of, hear_ahead, ready_open
from core.buy_mode.script_engine.method import ANY
from core.infra.utils import is_question, opens_question, tokenize


@dataclass(frozen=True)
class Verdict:
    kind: str           # nudge | says_nothing | ready | sense | objection | fact | question | answer
    name: str = ""      # which sense, objection or fact
    text: str = ""      # the reply without a nudge on its end
    asking: bool = False
    ahead: object = None  # the state with answers to later steps kept ("I want 5k a month"), else None

    @property
    def heard_as(self):
        return f"{self.kind}:{self.name}" if self.name else self.kind


def answer_labels(step):
    """The step's labelled answers: {label: [example, ...]}; empty when any reply is its answer."""
    return {r.label: list(r.examples) for r in step.listen if r.examples}


class Ear:
    """Hears a reply against the call so far. Order matters and lives here only: a nudge on its own, then a
    shrug, then an interruption that clearly beats an answer, then a question
    the step's own answers don't cover, else an answer."""

    def __init__(self, cfg, method, offer, sense, listener, shrugs, judge):
        """`judge(reply, {name: [examples]})`: the AI's pick of one name, or VAGUE."""
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._listener, self._shrugs, self._judge = listener, shrugs, judge

    def is_question(self, text):
        return is_question(text, self.cfg)

    def hear(self, text, state, opened):
        step = self.method.steps[state.step]
        rest = self._unnudged(text)
        if rest is not None and not tokenize(rest):
            return Verdict("nudge", text=text)  # "ok, what's next?": no answer
        text = text if rest is None else rest  # "credit, what's next?": the rest answers
        asking = self.is_question(text)
        if (asking and step.needs and len(tokenize(text)) <= self.cfg["rise_answer_words"]
                and not opens_question(text, self.cfg) and re.search(step.needs, text, re.IGNORECASE)):
            asking = False  # "dunno, a year?" to "how long?": the answer said with a rise, not a question
        if (not state.waiting and not self._yes_or_no(state) and self._shrugs.says_nothing(text, step, asking)
                and not self._ready(text, state)):  # "yes I'm in" is a shrug's words, but it says they're in
            return Verdict("says_nothing", text=text, asking=asking)  # an answer only: never an interruption
        ahead = None if asking else hear_ahead(self.method, state, text)  # "do I need 5k?" is not their goal
        ahead = None if ahead is state else ahead
        kind, name = self._interrupt(self._shrugs.unhedged(text), step, ahead or state, opened, asking)
        if kind:
            return Verdict(kind, name, text, asking, ahead)
        if asking and not self._answers(text, step):
            return Verdict("question", text=text, asking=asking, ahead=ahead)
        return Verdict("answer", text=text, asking=asking, ahead=ahead)

    def _yes_or_no(self, state):
        """The step was last asked as a yes-or-no question ("Is there anything you've tried?"): "yes" answers it."""
        words = tokenize(question_of(asked_line(self.method, state)[0]))
        return bool(words) and words[0] in self.cfg["closed_question_starts"]

    def _ready(self, text, state):
        """The reply says they're ready to buy, at a step where they may skip ahead."""
        ready = self.method.ready
        return (ready_open(self.method, state.step)
                and self._listener.match(text, {"ready": list(ready.examples)}, by_clause=False).score >= ready.min_score)

    def _unnudged(self, text):
        """The reply without a nudge on its end ("credit, what's next?" -> "credit"); None when it has none."""
        for phrase in sorted(self.sense.nudges, key=len, reverse=True):
            words = r"\W+".join(map(re.escape, tokenize(phrase)))
            leads = "|".join(map(re.escape, self.cfg["nudge_leads"]))
            found = re.search(rf"(?:^|\W)(?:(?:{leads})\W+)?{words}\W*$", text, re.IGNORECASE)
            if found:
                return text[:found.start()].rstrip(" ,;:-")
        return None

    def _interrupt(self, text, step, state, opened, asking):
        """An everyday interruption, product question or objection - only when it clearly beats
        reading the reply as an answer to the step's own question, like a human closer would."""
        senses = {k: i for k, i in self.sense.interruptions.items() if state.waiting or not i.after_wait}
        labels = {f"sense:{k}": i.examples for k, i in senses.items()}
        floors = {f"sense:{k}": i.min_score for k, i in senses.items()}  # lowest score a label counts at
        if asking:
            labels.update({f"fact:{k}": f.examples for k, f in self.offer.facts.items()})
        objections = self.method.objections.items()
        if not opened and step.doubts_answer and not asking:
            objections = ()  # "money's tight" answers "what holds you back"; "is this a scam?" still asks
        elif not opened and asking:
            objections = [(k, o) for k, o in objections if o.early]  # "is this a scam?" gets an honest early line
        if not opened:
            objections = [(k, o) for k, o in objections if k not in state.parked]  # parked once: never twice
        handled = set()  # a worry already being handled, or one the step asks about ("the money?"), answers the step
        if opened:
            handled = {k for k, _ in objections if k in state.raised or k in {r.label for r in step.listen}}
        labels.update({f"objection:{k}": o.examples for k, o in objections})
        objections = [(k, o) for k, o in objections if k not in handled]
        if not opened and not asking:  # "money", "scared", "risk" before the price are answers, not objections
            floors.update({f"objection:{k}": self.cfg["early_objection_min_score"] for k, _ in objections})
        if ready_open(self.method, state.step):
            labels["ready:prospect"] = self.method.ready.examples
            floors["ready:prospect"] = self.method.ready.min_score
        takes_any = any(r.label == ANY for r in step.listen)
        won = self._listener.interruption(text, labels, answer_labels(step), takes_any, asking, floors)
        if won and won.split(":", 1)[1] in handled:  # still kept as a label so a near worry can't win in its place
            won = None   # live: "I don't have 5k lying around" in the money talk was heard as "think it over"
        if not won and not opened and not asking:
            won = self._judged_objection(text, step, dict(objections))
        return tuple(won.split(":", 1)) if won else (None, "")

    def _judged_objection(self, text, step, objections):
        """An objection that scored in the grey band before the price ("10k seems like a lot", 0.81): too close
        to the step's answers for the embedder alone, so the AI picks objection or answer. AI down = answer."""
        found = self._listener.match(text, {k: o.examples for k, o in objections.items()})
        if not found.label or found.score < self.cfg["early_objection_judge_score"]:
            return None
        answers = [f"answering '{question_of(step.say_plain or step.say)}'"]  # the question asked, so the AI judges in context
        examples = objections[found.label].examples
        nearest = self._listener.match(text, {e: [e] for e in examples}).candidates  # the AI sees the closest ones
        pick = self._judge(text, {f"{found.label} objection": list(nearest) or examples, "answer": answers})
        return f"objection:{found.label}" if pick == f"{found.label} objection" else None

    def _answers(self, text, step):
        """The reply matches one of the step's own answers, even with a question in it ("yeah makes
        sense, what's next?" at the temp check), only when sure: "what happens to the card?" asks about the
        card, it doesn't choose it. Two answers too close to call are judged as usual."""
        labels = answer_labels(step)
        return bool(labels) and self._listener.answer_score(text, labels, asking=True) > 0
