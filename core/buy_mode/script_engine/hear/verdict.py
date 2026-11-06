"""What one prospect reply was heard as, before anything is said back: one `Verdict` per turn."""

import re
from dataclasses import dataclass

from core.buy_mode.script_engine.engine import asked_line, question_of, hear_ahead, ready_open
from core.buy_mode.script_engine.hear.reply import Reader
from core.buy_mode.script_engine.method import ANY
from core.infra.utils import tokenize


@dataclass(frozen=True)
class Verdict:
    kind: str           # nudge | says_nothing | ready | sense | objection | fact | question | answer
    name: str = ""      # which sense, objection or fact
    text: str = ""      # what they meant (reply.py): no nudge on its end, no hedge; an answer's content only
    asking: bool = False
    ahead: object = None  # the state with answers to later steps kept ("I want 5k a month"), else None
    side: str = ""      # an answer with a question beside it: how the question was heard ("fact:price", "question")
    asked: str = ""     # that question's words

    @property
    def heard_as(self):
        heard = f"{self.kind}:{self.name}" if self.name else self.kind
        return f"{heard}+{self.side}" if self.side else heard


def answer_labels(step):
    """The step's labelled answers: {label: [example, ...]}; empty when any reply is its answer."""
    return {r.label: list(r.examples) for r in step.listen if r.examples}


class Ear:
    """Hears a reply against the call so far, from its parts (reply.py). Order matters and lives here only: a
    nudge on its own; an answer with a question beside it (both kept); then a shrug, an interruption that
    clearly beats an answer, a question the step's own answers don't cover, else an answer."""

    def __init__(self, cfg, method, offer, sense, listener, shrugs, judge):
        """`judge(reply, {name: [examples]})`: the AI's pick of one name, or VAGUE."""
        self.cfg, self.method, self.offer, self.sense = cfg, method, offer, sense
        self._listener, self._shrugs, self._judge = listener, shrugs, judge
        self.reader = Reader(cfg, sense.nudges, shrugs.hedges)

    def hear(self, text, state, opened):
        step = self.method.steps[state.step]
        reply = self.reader.read(text).settle(lambda part: self._rises(part, step))
        if reply.nudged and not tokenize(reply.unnudged):
            return Verdict("nudge", text=text)  # "what's next?": no answer
        asking = bool(reply.asked)
        if asking and reply.said:
            both = self._with_side(reply, step, state, opened)
            if both:
                return both
        text = reply.said if reply.said and not asking else reply.meant  # "dunno, a year?" -> "a year"
        if (not state.waiting and not self._yes_or_no(state) and self._shrugs.says_nothing(text, step, asking)
                and not self._ready(text, state)):  # "yes I'm in" is a shrug's words, but it says they're in
            return Verdict("says_nothing", text=text, asking=asking)  # an answer only: never an interruption
        ahead = None if asking else hear_ahead(self.method, state, text)  # "do I need 5k?" is not their goal
        ahead = None if ahead is state else ahead
        kind, name = self._interrupt(text, step, ahead or state, opened, asking)
        if kind:
            return Verdict(kind, name, text, asking, ahead)
        if asking and not self._answers(text, step):
            return Verdict("question", text=text, asking=asking, ahead=ahead)
        return Verdict("answer", text=text, asking=asking, ahead=ahead)

    def _rises(self, part, step):
        """A part ending in "?" that isn't phrased as a question is the answer said with a rise when it is short
        and has the step's shape ("dunno, a year?" to "how long?"); else it asks ("what's this going to cost me?")."""
        return bool(step.needs) and len(tokenize(part)) <= self.cfg["rise_answer_words"] and self.shaped(part, step)

    def _with_side(self, reply, step, state, opened):
        """Content that answers the step, beside a question a one-line reply covers ("i guess 3 years, what
        about you?", "nothing, why do you ask?"): the answer is kept and the question answered in front of the
        next line. A worry in the content leads instead ("5k? that's a lot"). None, so the question leads as
        it always did, when the question is a worry after the price, "say that again?", a shortcut, or itself
        one of the step's answers beside a worry, after a pause, or when the content is no answer. A question that
        picks one of the step's answers beside a plain one ("yeah I'm in, how do I pay?") is that answer, heard alone."""
        if state.waiting:
            return None  # "ok I'm back, where were we" after a pause
        picked = self._chooses(reply.asked, step)
        if picked:  # "yeah I'm in, how do I pay?": the question is the answer, heard alone, unless the content
            # takes it back ("no, credit?": torn, judged as before) or is a worry ("that's a lot, how do I pay?")
            if self._takes_back(reply.said, picked, step) or self._interrupt(reply.said, step, state, opened, False)[0]:
                return None
            return Verdict("answer", text=reply.asked, asking=True)
        kind, name = self._interrupt(reply.asked, step, state, opened, True)
        if (kind == "ready" or (kind == "objection" and opened)
                or (kind == "sense" and not self.sense.interruptions[name].with_answer)):  # "say that again?" leads
            return None
        within, about = self._interrupt(reply.said, step, state, opened, False)
        if within:  # the content is itself a worry or a sense, no answer: "that's a lot", "shut up"
            # a worry leads ("5k? that's a lot": the money, not the price again); a sense leads only beside a
            # plain question ("shut up and just tell me the price" wants the price)
            return Verdict(within, about, reply.said) if within == "objection" or not kind else None
        if not self._answers_step(reply.said, step, state):
            return None
        ahead = hear_ahead(self.method, state, reply.said)
        return Verdict("answer", text=reply.said, asking=True, ahead=None if ahead is state else ahead,
                       side=f"{kind}:{name}" if kind else "question", asked=reply.asked)

    def _chooses(self, question, step):
        """The one label of the step's answers the question surely picks on its own ("how do I pay?" at the
        close), else "": not torn between two ("how much is it anyway" is near two goal levels and picks neither)."""
        labels = answer_labels(step)
        found = self._listener.match(question, labels) if labels else None
        sure = found and found.label and not found.close and found.score >= self.cfg["question_answer_min_score"]
        return found.label if sure else ""

    def _takes_back(self, said, label, step):
        """The content is another of the step's answers, one that says no (`takes_back`: "no", "not yet"):
        beside "how do I pay?" it takes the question back. "yeah I'm in" doesn't."""
        found = self._listener.match(said, answer_labels(step))
        if not (found and found.label) or found.label == label:
            return False
        return next(r for r in step.listen if r.label == found.label).like in self.cfg["takes_back"]

    def _answers_step(self, text, step, state):
        """`text` is an answer the step keeps: its shape, not a shrug, and one of its answers or any reply."""
        if not self.shaped(text, step):
            return False
        if self._shrugs.says_nothing(text, step, False) and not self._yes_or_no(state):
            return False
        labels = answer_labels(step)
        if labels and self._listener.answer(text, labels, list(self.sense.unclear),
                                            {r.label: r.min_score for r in step.listen if r.label}).label:
            return True
        return any(r.label == ANY for r in step.listen)

    @staticmethod
    def shaped(text, step):
        """The reply has the shape the step's answer needs (`needs`: a figure, a span of time), or it needs none."""
        return not step.needs or bool(re.search(step.needs, text, re.IGNORECASE))

    def _yes_or_no(self, state):
        """The step was last asked as a yes-or-no question ("Is there anything you've tried?"): "yes" answers it."""
        words = tokenize(question_of(asked_line(self.method, state)[0]))
        return bool(words) and words[0] in self.cfg["closed_question_starts"]

    def _open(self, step_id):
        """{name: Ready} for the shortcuts open at this step."""
        return {k: r for k, r in self.method.shortcuts.items() if ready_open(self.method, step_id, r)}

    def _ready(self, text, state):
        """The reply takes a shortcut open at this step ("yes I'm in", "credit")."""
        return any(self._listener.match(text, {"ready": list(r.examples)}, by_clause=False).score >= r.min_score
                   for r in self._open(state.step).values())

    def _interrupt(self, text, step, state, opened, asking):
        """An everyday interruption, product question or objection - only when it clearly beats
        reading the reply as an answer to the step's own question, like a human closer would."""
        # "not sure" alone is not knowing, not asking what we meant: no sense that rephrases hears a hedge
        hedge = not asking and self._shrugs.hedges(text)
        senses = {k: i for k, i in self.sense.interruptions.items()
                  if (state.waiting or not i.after_wait) and not (hedge and i.after == "rephrase")}
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
        for k, r in self._open(state.step).items():
            labels[f"ready:{k}"], floors[f"ready:{k}"] = r.examples, r.min_score
        # the catch-all keeps any reply only if it has the step's shape: "I don't have time for this" to "how
        # long?" can't be the answer, so nothing has to out-score it there (live: the frustration went unheard)
        takes_any = any(r.label == ANY for r in step.listen) and self.shaped(text, step)
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
