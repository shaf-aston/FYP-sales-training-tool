"""One selling turn: the script picks the line, the AI only fills small checked gaps."""

from dataclasses import asdict, replace
from functools import lru_cache, partial
from pathlib import Path

from core.loader import load_yaml
from core.script_engine.ai_gate import AiGate
from core.script_engine.config import check
from core.script_engine.echo import Echo
from core.script_engine.embedder import make_embedder
from core.script_engine.engine import (
    advance,
    ScriptState,
    ask_again,
    asked_line,
    asks_left,
    jump,
    move_on,
    object_to,
    park,
    price_open,
    start,
)
from core.script_engine.fill import Filler, fix_typos
from core.script_engine.judge import VAGUE
from core.script_engine.method import load_common_sense, load_meanings, load_method, load_offer
from core.script_engine.recognise import Listener
from core.script_engine.shrug import Shrugs
from core.script_engine import tone
from core.script_engine.verdict import Ear, answer_labels
from core.script_engine.voice import Voice
from core.utils import tokenize

from ..logs import timed

ROOT = Path(__file__).resolve().parent.parent.parent


def engine_config():
    return load_yaml("script/engine.yaml")


@lru_cache(maxsize=1)
def shared_embedder():
    """One model per process: loading it is the slow part."""
    return make_embedder(engine_config(), ROOT)


@lru_cache(maxsize=1)
def shared_gate():
    """One AI gate per process: its failure breaker is shared by every call on purpose."""
    return AiGate(engine_config())


def resolve_product(product):
    """The product to sell: the one asked for if it is scripted, else the default."""
    cfg = engine_config()
    return product if product in cfg["products"] else cfg["default_product"]


def build_seller(router, product, embedder=None, gate=None):
    cfg = engine_config()
    entry = cfg["products"][product]
    return ScriptSeller(
        cfg, load_method(entry.get("method", cfg["method"])), load_offer(entry["offer"]), load_common_sense(),
        embedder or shared_embedder(), (gate or shared_gate()).llm(router), load_meanings(),
    )


class ScriptSeller:
    def __init__(self, cfg, method, offer, sense, embedder, llm, meanings=None):
        """`llm`: a `Voice`, or a plain `llm(prompt, max_tokens)` callable wrapped in one.
        `meanings`: the meaning bank (method.py `Meanings`); None = the one in config/script."""
        self.cfg, self.method, self.offer, self.sense = check(cfg), method, offer, sense
        self._listener = Listener(cfg, embedder)
        self._voice = llm if hasattr(llm, "new_turn") else Voice(cfg, offer, llm)
        self._opening = start(method)
        self.state = self._opening.state
        examples = self._script_examples()
        vocab = frozenset(w for e in examples for w in tokenize(e)) | frozenset(cfg["spell_words"])
        self._vocab = vocab
        echo = frozenset(s.capture for s in method.steps.values() if s.echo) | {"said"}  # {said}: sense.ask_meaning
        self._filler = Filler(cfg, offer, echo, vocab)
        self._shrugs = Shrugs(cfg, sense, self._listener, self._filler.fill)
        self._ear = Ear(cfg, method, offer, sense, self._listener, self._shrugs)
        self._echo = Echo(cfg, meanings or load_meanings(), self._listener)
        self._turn = Echo.new_turn(self.state)
        embedder.warm(examples + self._echo.examples())

    def _script_examples(self):
        found = [e for i in self.sense.interruptions.values() for e in i.examples] + list(self.sense.unclear)
        found += [e for f in self.offer.facts.values() for e in f.examples]
        found += [e for o in self.method.objections.values() for e in o.examples]
        found += [e for s in self.method.steps.values() for r in s.listen for e in r.examples]
        found += list(self.method.ready.examples) if self.method.ready else []
        return found

    def reset(self, state=None):
        self.state = state or self._opening.state

    def snapshot(self):
        """Everything the call needs to carry on from here, as plain data (kept per turn for rewinds)."""
        return asdict(self.state)

    def restore(self, saved=None):
        """Back to a `snapshot()`; None goes back to the opening."""
        if saved:  # JSON gives lists back: tuples, so `said + (line,)` still adds up
            saved = {**saved, **{k: tuple(saved.get(k, ())) for k in ("said", "parked", "raised", "echoed", "meant")}}
        self.reset(ScriptState(**saved) if saved else None)

    def opening(self):
        """The first line of the call: (text, ui_stage)."""
        self._voice.new_turn()
        self._turn = Echo.new_turn(self.state)
        text = self._render(self._opening)
        self.state = Echo.settle(self.state, self._turn)
        return text, self._opening.ui_stage

    # ---- one turn -------------------------------------------------------------------------

    @timed
    def reply(self, text):
        """Answer one prospect message. Returns (text, ui_stage). `self.last_turn` then says what the
        reply was heard as and where the script went, for the turn log."""
        before = self.state.step
        said, ui_stage, heard_as = self._reply(fix_typos(text, self._vocab, self.cfg))
        self.last_turn = {"step_from": before, "step_to": self.state.step, "heard_as": heard_as,
                          "saved": {k: v for k, v in self.state.slots.items() if v}}
        return said, ui_stage

    def _reply(self, text):
        """(text, ui_stage, heard_as): hear the reply, then answer what it was heard as."""
        self._voice.new_turn()
        self._turn = Echo.new_turn(self.state)
        step = self.method.steps[self.state.step]
        opened = price_open(self.method, self.state.step)
        v = self._ear.hear(text, self.state, opened)
        self.state = replace(v.ahead or self.state, waiting=False)  # early answers are kept whatever it was
        said, ui_stage, detail = self._respond(v, step, opened)
        self.state = Echo.settle(self.state, self._turn)
        return said, ui_stage, detail or v.heard_as

    def _respond(self, v, step, opened):
        """(text, ui_stage, heard_as detail or "")."""
        if v.kind == "nudge":
            return *self._carry_on(self.sense.nudge, step, rephrase=False), ""
        if v.kind == "says_nothing":
            move, _, detail = self._listen(v, step, opened, empty=True)
            self.state = move.state
            return self._render(move), move.ui_stage, detail
        if v.kind == "ready":
            return *self._go(jump(self.method, self.state, self.method.ready.then)), ""
        if v.kind == "sense":
            return *self._sense(self.sense.interruptions[v.name], step), ""
        if v.kind == "objection" and not opened:
            self.state = park(self.state, v.name)
            return self._then_ask(self.method.objections[v.name].early or self.sense.park), step.ui_stage, ""
        if v.kind == "objection":
            return *self._object(v.name), ""
        if v.kind == "fact":
            f = self.offer.facts[v.name]
            lead = self._filler.fill(f.late_answer if opened and f.late_answer else f.answer, {})
            return self._then_ask(lead), step.ui_stage, ""
        if v.kind == "question":
            answer = self._answer_uncovered(v.text, opened) or self.cfg["uncovered_fallback"]
            return self._then_ask(answer), step.ui_stage, ""
        return self._answer(v, step, opened)

    def _answer(self, v, step, opened):
        text = v.text
        move, ack, heard_as = self._listen(v, step, opened)
        if self._hesitates(move):
            return self._revisit(), step.ui_stage, "hesitates"
        earlier = self._earlier(step)
        self.state = move.state
        # an answer with a question in it: the question gets an answer when the facts have one, else
        # nothing ("what's next?" needs none). After the judge: a failed AI line can't cost it.
        heard = self._answer_uncovered(text, opened) if v.asking else ""
        react = None
        acked = move.ack and self._filler.fill(move.ack, move.state.slots) is not None  # "{months} months..." needs a number
        if not heard and not acked and move.state.step != step.id:
            react = partial(self._react, text, step, ack, earlier, opened)  # run after the question: it may quote them first
        return self._render(move, heard, react), move.ui_stage, heard_as

    def _react(self, text, step, ack, earlier, opened):
        """What shows their answer was heard: (line, own bubble). A meaning line first (no AI, and no quoting
        them); else the AI's "I heard you" line, which says their words back, so only when the echo budget
        allows it; else nothing."""
        line = self._echo.meaning(text, self.state, self._turn)
        if line:
            self._turn.meant += (line,)
            return line, True
        if not self._echo.may_quote(self._turn, self.state, (), False):
            return "", False
        if ack is None:
            ack = self._voice.ack(text, step.say_plain or step.say, earlier, opened)
        if ack and self._echo.quotes(ack, text):
            self._turn.quoted = True
        return ack, False

    def _earlier(self, step):
        """Their answers to the other steps: what an AI line may link to."""
        return {k: v for k, v in self.state.slots.items() if k != step.capture}

    def _go(self, move):
        """Take a move as it is: no "I heard you" line in front of it."""
        self.state = move.state
        return self._render(move), move.ui_stage

    def _sense(self, said, step):
        """An everyday interruption: its reply, then what its `after` says."""
        if said.after == "wait":
            self.state = replace(self.state, waiting=True)
            return said.reply, step.ui_stage
        if said.after == "ask":
            return self._then_ask(said.reply), step.ui_stage
        return self._carry_on(said.reply, step, rephrase=said.after == "rephrase")

    def _carry_on(self, lead, step, rephrase):
        """`lead`, then the step in other words; a step with no other words moves on instead (without
        taking the reply as its answer), so the same line is never said twice in a row."""
        if rephrase or step.probes:
            move = ask_again(self.method, self.state)
        else:
            move = move_on(self.method, self.state)
        text, stage = self._go(move)
        return f"{lead} {text}", stage

    def _hesitates(self, move):
        """They held back at the revisit step (asked again, or given up on) while a worry from earlier is
        still unanswered."""
        step_id = self.method.revisit_step
        return (self.state.step == step_id and bool(self.state.parked)
                and move.state.step in (step_id, self.method.steps[step_id].stuck.then))

    def _revisit(self):
        """Raise the oldest parked worry now: it is likely what holds them back."""
        text, _ = self._object(self.state.parked[0])
        return f"{self.sense.revisit} {text}"

    def _object(self, name):
        """Handle an objection after the price by its matrix branch."""
        return self._go(object_to(self.method, self.state, name, self.cfg["objection_entries"]))

    def ui_stage(self):
        """The UI stage of the step the call is on."""
        return self.method.steps[self.state.step].ui_stage

    def coach_notes(self):
        """Notes for the learner, straight from the script step - no AI, instant."""
        step = self.method.steps[self.state.step]
        title = f"{step.id} {step.name}".strip() if step.name else step.id
        notes = self.cfg["coach_notes"]
        return {
            "what_happened": notes["step"].format(title=title, name=(step.name or step.id).lower()),
            "next_move": notes["listen"].format(note=step.note) if step.note else notes["default"],
        }

    @timed
    def _listen(self, v, step, opened, empty=False):
        """Hear the reply as the step's answer: (move, ack, heard_as detail). ack = the AI's "I heard you"
        line from the listen call ("" when it failed a check), or None when no listen call was made."""
        text, labels = v.text, answer_labels(step)
        label, line, ack, missed = None, "", None, False
        if labels:
            found = self._listener.match(text, labels)
            label = found.label
            if label and found.score < next(r.min_score for r in step.listen if r.label == label):
                label = None  # under the route's own floor: heard as no labelled answer
            if found.close:
                pick = self._voice.judge(text, {c: labels[c] for c in found.candidates})
                label = None if pick == VAGUE else pick
                if found.label and not label and step.unsure and all(r.then != step.id for r in step.listen if r.label in found.candidates):
                    label = step.unsure  # every near meaning is a real answer: take the step's safe one, don't ask again
        elif self.cfg["listen"] and step.capture and not (empty and not asks_left(self.method, self.state, self.cfg["misses"])):
            concept = f"{step.name}: {step.note}" if step.note else step.name  # the AI hears for it
            heard = self._voice.listen(text, concept, self._question(), self._earlier(step), opened)
            if heard is not None:
                missed = not heard.answered
                empty, line, ack = empty or missed, heard.probe, heard.ack
        if step.capture and not line:
            line = self._shrugs.ask_meaning(text, self._question(), empty, v.ahead is not None,
                                            self.state.slots.values())  # said only if asked again
        detail = ""
        if missed:
            detail = "misses"
        elif v.kind == "answer":
            detail = f"answer:{label}" if label else ("answer:any" if not labels else "answer:unclear")
        return advance(self.method, self.state, label, text, empty, line, self.cfg["misses"]), ack, detail

    def _question(self):
        """The step's question as it was just asked, blanks filled."""
        asked, plain = asked_line(self.method, self.state)
        return tone.plain(self._filler.fill(asked, self.state.slots) or plain
                          or self.method.steps[self.state.step].say_plain or asked)

    @timed
    def _answer_uncovered(self, question, opened):
        """A short answer to a product question nothing covers, from the offer's facts and what they told us.
        It may say anything the facts support, never a new number, promise or price: always checked and
        logged. None when the facts don't cover it (the caller decides whether to say the fallback)."""
        offer = self.offer
        if not offer.about:
            return None
        facts = self._filler.fill(offer.about, {})
        if opened and offer.about_after_price:
            facts += " " + self._filler.fill(offer.about_after_price, {})
        return self._voice.answer(question, facts, self.state.slots, opened)

    def _then_ask(self, lead):
        """`lead`, then the current question again. A step that asks nothing (a statement) is not
        said again: a fact answered at a statement step said the statement twice."""
        say, say_plain = asked_line(self.method, self.state)  # the words last used, not always the first
        question = self._line(self.method.steps[self.state.step], say, "", say_plain, self.state.slots)
        if "?" not in question:
            question = ""
        return f"{lead.strip()} {question.strip()}".strip()

    def _render(self, move, heard="", react=None):
        """The message: `heard` (or what `react()` gives, decided after the lines it leads into), then any
        run_on steps, then the step's line."""
        said = []
        for step_id in move.lead:
            lead = self.method.steps[step_id]
            said.append(self._line(lead, lead.say, "", lead.say_plain, move.state.slots))
        step = self.method.steps[move.state.step]
        said.append(self._line(step, move.say, move.ack, step.say_plain, move.state.slots))
        text = " ".join(said)
        heard, bubble = react() if react else (heard, False)
        if not heard:
            return text
        return tone.join(heard, text) if bubble else f"{heard} {text}"

    def _line(self, step, say, ack, say_plain, slots):
        """One line as said, within the echo budget (echo.py): their words where it allows, else the plain line."""
        phrases = self._filler.echoes(say, slots) + self._filler.echoes(ack, slots)
        if phrases and not self._echo.may_quote(self._turn, self.state, phrases, step.moment):
            slots, phrases = {k: v for k, v in slots.items() if k not in self._filler.echo}, []
        if phrases:
            Echo.said(self._turn, phrases)
        return self._filler.render(say, ack, say_plain, slots)
