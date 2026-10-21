"""What one prospect reply was heard as, before anything is said back: one `Verdict` per turn."""

import re
from dataclasses import dataclass

from core.script_engine.engine import hear_ahead, ready_open
from core.script_engine.method import ANY
from core.utils import is_question, tokenize


@dataclass(frozen=True)
class Verdict:
    kind: str           # nudge | says_nothing | ready | sense | objection | fact | play | question | answer
    name: str = ""      # which sense, objection, fact or objection play
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
    shrug, then an interruption that clearly beats an answer, then an open objection play, then a question
    the step's own answers don't cover, else an answer."""

    def __init__(self, cfg, method, offer, sense, listener, shrugs):
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._listener, self._shrugs = listener, shrugs

    def is_question(self, text):
        return is_question(text, self.cfg["question_starts"], self.cfg["filler_tags"])

    def hear(self, text, state, opened):
        step = self.method.steps[state.step]
        rest = self._unnudged(text)
        if rest is not None and not tokenize(rest):
            return Verdict("nudge", text=text)  # "ok, what's next?": no answer
        text = text if rest is None else rest  # "credit, what's next?": the rest answers
        asking = self.is_question(text)
        if not state.waiting and not state.play and self._shrugs.says_nothing(text, step, asking):
            return Verdict("says_nothing", text=text, asking=asking)  # an answer only: never an interruption
        ahead = None if asking else hear_ahead(self.method, state, text)  # "do I need 5k?" is not their goal
        ahead = None if ahead is state else ahead
        kind, name = self._interrupt(text, step, ahead or state, opened, asking)
        if kind:
            return Verdict(kind, name, text, asking, ahead)
        if state.play:
            return Verdict("play", state.play, text, asking, ahead)
        if asking and not self._answers(text, step):
            return Verdict("question", text=text, asking=asking, ahead=ahead)
        return Verdict("answer", text=text, asking=asking, ahead=ahead)

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
        if not opened and step.doubts_answer:
            objections = ()  # "money's tight" answers "what holds you back"
        elif not opened and asking:
            objections = [(k, o) for k, o in objections if o.early]  # "is this a scam?" gets an honest early line
        if not opened:
            objections = [(k, o) for k, o in objections if k not in state.parked]  # parked once: never twice
        labels.update({f"objection:{k}": o.examples for k, o in objections})
        if not opened and not asking:  # "money", "scared", "risk" before the price are answers, not objections
            floors.update({f"objection:{k}": self.cfg["early_objection_min_score"] for k, _ in objections})
        if ready_open(self.method, state.step):
            labels["ready:prospect"] = self.method.ready.examples
            floors["ready:prospect"] = self.method.ready.min_score
        takes_any = any(r.label == ANY for r in step.listen)
        won = self._listener.interruption(text, labels, answer_labels(step), takes_any, asking, floors)
        return tuple(won.split(":", 1)) if won else (None, "")

    def _answers(self, text, step):
        """The reply matches one of the step's own answers, even with a question in it ("yeah makes
        sense, what's next?" at the temp check). Two answers too close to call are judged as usual."""
        labels = answer_labels(step)
        return bool(labels) and self._listener.match(text, labels).label is not None
