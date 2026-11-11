"""One selling turn: the script picks the line, the AI only fills small checked gaps."""

import logging
import re
from dataclasses import asdict, replace
from functools import lru_cache

from core.buy_mode.script_engine.ai.gate import AiGate
from core.buy_mode.script_engine.ai.judge import VAGUE
from core.buy_mode.script_engine.ai.voice import Voice
from core.buy_mode.script_engine.config import check
from core.buy_mode.script_engine.engine import (
    ScriptState,
    advance,
    asked_line,
    asks_left,
    carry_on,
    jump,
    move_on,
    object_to,
    park,
    price_open,
    question_of,
    start,
)
from core.buy_mode.script_engine.hear.embedder import make_embedder
from core.buy_mode.script_engine.hear.meanings import MeaningBank, load_meanings
from core.buy_mode.script_engine.hear.recognise import Listener
from core.buy_mode.script_engine.hear.reply import after, clauses
from core.buy_mode.script_engine.hear.shrug import Shrugs
from core.buy_mode.script_engine.hear.verdict import Ear, answer_labels
from core.buy_mode.script_engine.method import (
    ANY,
    load_common_sense,
    load_method,
    load_offer,
)
from core.buy_mode.script_engine.words import tone
from core.buy_mode.script_engine.words.echo import Echo, Turn
from core.buy_mode.script_engine.words.fill import Filler, fix_typos
from core.infra.env import ROOT_DIR
from core.infra.loader import load_yaml
from core.infra.logs import timed
from core.infra.utils import tokenize

log = logging.getLogger(__name__)


def engine_config():
    return load_yaml("script/engine.yaml")


@lru_cache(maxsize=1)
def shared_embedder():
    """One model per process: loading it is the slow part."""
    return make_embedder(engine_config(), ROOT_DIR)


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
        embedder or shared_embedder(), (gate or shared_gate()).llm(router),
    )


class ScriptSeller:
    def __init__(self, cfg, method, offer, sense, embedder, llm, meanings=None):
        """`llm`: a `Voice`, or a plain `llm(prompt, max_tokens)` callable wrapped in one.
        `meanings`: the meaning bank (meanings.py `Meanings`); None = the one in config/script."""
        self.cfg, self.method, self.offer, self.sense = check(cfg), method, offer, sense
        self._listener = Listener(cfg, embedder)
        self._voice = llm if hasattr(llm, "new_turn") else Voice(cfg, offer, llm)
        self._opening = start(method)
        self.state = self._start = self._opening.state  # `_start`: where the call began (the opening, or a jumped-to step)
        self.last_turn = {}  # what the latest reply was heard as: see `reply`
        examples = self._script_examples()
        vocab = frozenset(w for e in examples for w in tokenize(e)) | frozenset(cfg["spell_words"])
        self._vocab = vocab
        echo = frozenset(s.capture for s in method.steps.values() if s.echo) | {"said"}  # {said}: sense.ask_meaning
        self._filler = Filler(cfg, offer, echo, vocab)
        self._shrugs = Shrugs(cfg, sense, self._listener, self._filler.fill)
        self._ear = Ear(cfg, method, offer, sense, self._listener, self._shrugs, self._voice.judge)
        self._echo = Echo(cfg)
        self._meanings = MeaningBank(cfg, meanings or load_meanings(), self._listener)
        self._turn = Turn()
        self._leads = self._lead_lines()
        embedder.warm(examples + self._meanings.examples())

    def _lead_lines(self):
        """The fixed lines said in front of a question asked again: the `reask` leads, the replies of the
        senses that rephrase ("Fair point, let me put it another way.") or sit beside an answer (round 101: "There's
        no right answer here" three times a call) and the same worry asked again."""
        lines = set(self.method.reask) | {line for s in self.method.steps.values() for line in s.reask}
        lines |= {i.reply for i in self.sense.interruptions.values() if i.after.startswith("rephrase") or i.with_answer}
        lines |= {self.sense.same_words, self.sense.park_again, *self.sense.yes_no_reask}
        return sorted(line for line in lines if line)

    def _wear(self, text):
        """A lead line said `lead_repeats` times this call is left out after that: the same lead again and
        again sounds like a loop ("Fair enough, I'll keep this quick." x20). Never the whole message."""
        for line in self._leads:
            if line not in text:
                continue
            rest = re.sub(r" {2,}", " ", text.replace(line, "", 1)).strip()
            if self.state.spoken.count(line) >= self.cfg["lead_repeats"] and rest:
                text = rest
            else:
                self.state = replace(self.state, spoken=self.state.spoken + (line,))
        return text

    def _script_examples(self):
        found = [e for i in self.sense.interruptions.values() for e in i.heard(False)] + list(self.sense.unclear)
        found += [e for f in self.offer.facts.values() for e in f.examples]
        found += [e for o in self.method.objections.values() for e in o.examples]
        found += [e for s in self.method.steps.values() for r in s.listen for e in r.examples]
        found += [e for r in self.method.shortcuts.values() for e in r.examples]
        return found

    def reset(self, state=None):
        self.state = state or self._start

    def steps(self):
        """The steps a call can start at, in script order: those with a line to say (id and name)."""
        return [{"id": s.id, "name": s.name or s.id} for s in self.method.steps.values() if s.say]

    def start_at(self, step_id):
        """Start the call fresh at `step_id` (testing one step): nothing heard before, so no answers to build
        on; its line falls back to its plain words. Returns (text, ui_stage). ValueError for a step with no line."""
        step = self.method.steps.get(step_id)
        if not step or not step.say:
            raise ValueError(f"no step to start at: {step_id!r}")
        self._voice.new_turn()
        self._turn = Turn()
        self.state = ScriptState(step=step_id)
        text, ui_stage = self._go(jump(self.method, self.state, step_id))
        self.state = self._start = replace(Echo.settle(self.state, self._turn), last=text)
        return text, ui_stage

    def snapshot(self):
        """Everything the call needs to carry on from here, as plain data (kept per turn for rewinds)."""
        return asdict(self.state)

    def restore(self, saved=None):
        """Back to a `snapshot()`; None goes back to the opening."""
        if saved:  # JSON gives lists back: tuples, so `said + (line,)` still adds up
            saved = {**saved, **{k: tuple(saved.get(k, ())) for k in ("said", "parked", "raised", "echoed", "meant", "told", "spoken", "seen")}}
        self.reset(ScriptState(**saved) if saved else None)

    def opening(self):
        """The first line of the call: (text, ui_stage)."""
        self._voice.new_turn()
        self._turn = Turn()
        text = self._render(self._opening)
        self.state = Echo.settle(self.state, self._turn)
        return text, self._opening.ui_stage

    # ---- one turn -------------------------------------------------------------------------

    @timed
    def reply(self, text):
        """Answer one prospect message. Returns (text, ui_stage). `self.last_turn` then says what the
        reply was heard as and where the script went, for the turn log."""
        before, saved = self.state.step, self.state
        if not tokenize(text):  # no words we can read (another language, emoji, symbols): ask again, stay put
            said, ui_stage, heard_as = self.sense.no_words, self.ui_stage(), "no_words"
        else:
            try:
                said, ui_stage, heard_as = self._reply(fix_typos(text, self._vocab, self.cfg))
            except Exception:  # blanket: any fault in hearing → same step, one safe line, never a crash
                log.exception("script reply failed")
                self.state = saved
                said, ui_stage, heard_as = self.sense.no_words, self.ui_stage(), "error"
        self.last_turn = {"step_from": before, "step_to": self.state.step, "heard_as": heard_as,
                          "saved": {k: v for k, v in self.state.slots.items() if v}}
        return said, ui_stage

    def _reply(self, text):
        """(text, ui_stage, heard_as): hear the reply, then answer what it was heard as."""
        self._voice.new_turn()
        step = self.method.steps[self.state.step]
        if not step.routes and self.sense.ended:  # the call is over: "bye" again never re-books the follow-up
            return self.sense.ended, step.ui_stage, "ended"
        text, pending = (f"{self.state.pending} {text}" if self.state.pending else text), self.state.pending
        if not pending and self._unfinished(text):  # "probably the fact that": wait for the rest, once
            self.state = replace(self.state, pending=text, last=self.sense.unfinished)
            return self.sense.unfinished, step.ui_stage, "unfinished"
        self.state = replace(self.state, pending="")
        self._turn = Turn(text)
        opened = price_open(self.method, self.state.step)
        v = self._ear.hear(text, self.state, opened)
        bridged = self.state.bridged
        self.state = replace(v.ahead or self.state, waiting=False, bridged=False)  # early answers are kept whatever it was
        if bridged and v.kind in ("answer", "says_nothing"):  # their reply to the getting-to-know-you question
            said = self._then_ask(self.cfg["bridge_ack"])
            self.state = replace(self.state, last=said)
            return said, self.ui_stage(), "bridge"
        said, ui_stage, detail = self._respond(v, step, opened)
        remark = self.sense.interruptions.get(v.name if v.kind == "sense" else v.side.removeprefix("sense:"))
        if remark and remark.once and remark.reply in said:  # said once: the same remark again is heard as the rest (ear `_said_again`)
            self.state = replace(self.state, spoken=self.state.spoken + (remark.reply,))
        spoken = self.state.spoken
        said = self._wear(said)
        if said == self.state.last and "?" in said and self.state.step == step.id:  # word for word again: move on
            self.state = replace(self.state, spoken=spoken)  # the lead it wore was never said
            said, ui_stage = self._go(move_on(self.method, self.state))
            said = self._wear(said)
        said = self._fresh_opener(said)
        self.state = replace(Echo.settle(self.state, self._turn), repeated=self._turn.side, last=said)
        return said, ui_stage, detail or v.heard_as

    def _unfinished(self, text):
        """The reply stops mid-sentence: 2+ words, no end mark, the last word leaves it open ("the fact that")."""
        words = text.lower().rstrip().split()
        return (bool(self.sense.unfinished) and len(words) >= 2 and not text.rstrip()[-1:] in ".?!"
                and "," not in text.rstrip()[-1:]
                and any(words[-len(e.split()):] == e.split() for e in self.sense.unfinished_ends))

    def _fresh_opener(self, said):
        """An opener ("Okay.") that also opened the last message is left off: "Okay." four times in a row
        through the owner's lines reads as a tic. The rest is said as it is, capitalised."""
        for word in self.cfg["openers"]:
            rest = said[len(word):].lstrip(" .,")
            if said.startswith(word) and self.state.last.startswith(word) and rest:
                return rest[0].upper() + rest[1:]
        return said

    def _respond(self, v, step, opened):
        """(text, ui_stage, heard_as detail or "")."""
        if v.kind == "nudge":
            return *self._carry_on(self.sense.nudge), ""
        if v.kind == "says_nothing":
            move, _, detail = self._listen(v, step, opened, empty=True)
            self.state = move.state
            return self._render(move), move.ui_stage, detail
        if v.kind == "ready":
            move = jump(self.method, self.state, self.method.shortcuts[v.name].then)
            return *self._go(self._ends_there(move, v, opened)), ""
        if v.kind == "corrects":  # "sorry I meant 3k not 2k": the answer fixed, the question asked again
            self.state = replace(self.state, slots={**self.state.slots, v.name: v.text})
            return self._then_ask(self.sense.corrected), self.ui_stage(), ""
        if v.kind == "sense":
            return *self._sense(self.sense.interruptions[v.name]), ""
        if v.kind == "objection" and not opened:
            return self._then_ask(self._park(v.name)), self.ui_stage(), ""
        if v.kind == "objection":
            return *self._object(v.name), ""
        if v.kind == "fact":
            lead, fresh = self._fact(v.name, opened)
            if fresh and self.offer.facts[v.name].bridge and step.bridge:
                self.state = replace(self.state, bridged=True)
                return f"{lead} {step.bridge}", self.ui_stage(), ""
            return self._then_ask(lead), self.ui_stage(), ""
        if v.kind == "question":
            answer = self._answer_uncovered(v.text, opened) or self.cfg["uncovered_fallback"]
            return self._then_ask(answer), self.ui_stage(), ""
        said, ui_stage, detail = self._answer(v, step, opened)
        return said, ui_stage, f"{detail}+{v.side}" if detail and v.side else detail

    def _fact(self, name, opened):
        """A product fact's answer: (line, fresh). Asked again, a short reminder, never fresh: before the price
        its `again` (else "like I said", straight after the answer); pressed `fact_presses` times before the price, its `pressed` line once (Ivy: "how much is
        it?" got "the exact price comes once I know what you need" 30 times); once the price step is reached or
        the number is out, `late_answer`, then `late_again`. `told` keeps each telling ("price+" told late)."""
        f, told = self.offer.facts[name], self.state.told
        out = f"{name}+" in told
        if not opened and not out and f.pressed and told.count(name) + 1 >= self.cfg["fact_presses"]:
            line, key = f.pressed, f"{name}+"
        elif (opened or out) and f.late_answer:
            line, key = (f.late_again or f.late_answer) if out else f.late_answer, f"{name}+"
        elif name in told:  # "like I said a moment ago" only when it was: told long ago, the answer again
            line, key = f.again or self._unless_just_said(self._filler.fill(f.answer, {})), name
        else:
            line, key = f.answer, name
        self.state = replace(self.state, told=(*told, key))
        return self._filler.fill(line, {}), key not in told

    def _side(self, v, opened):
        """The line for the question beside an answer (`v.side`), said in front of the next one: a fact's
        answer, a sense's one line, a worry before the price acknowledged (and parked), else the AI's answer
        from the facts ("" when it has none: the answer still moves the call on)."""
        kind, _, name = v.side.partition(":")
        if kind == "fact" and not opened and price_open(self.method, self.state.step):
            return ""  # the answer reached the price step, which tells the offer: "how much is it?" needs no "later"
        if kind == "fact":
            return self._fact(name, opened)[0]
        if kind == "sense":  # said just before ("2k, is that enough?", "a year, is that long?"): the reminder (round 81)
            reply = self.sense.interruptions[name].reply
            return self._unless_just_said(reply)
        if kind == "objection":
            return self._park(name)
        return self._answer_uncovered(v.asked, opened) or ""

    def _unless_just_said(self, line, reminder=None):
        """`line`, or the short reminder (default `told_again`) when the last message already said it: the same
        words twice in a row read as a recording (round 81: "2k, is that enough?" twice)."""
        reminder = self.sense.told_again if reminder is None else reminder
        return reminder if line and reminder and line in self.state.last else line

    def _park(self, name):
        """A worry before the price: its honest early line (or `park`), parked for the close. Asked about again,
        `park_again`: the same long line twice reads as a recording."""
        again = name in self.state.parked and self.sense.park_again
        self.state = park(self.state, name)
        return again or self.method.objections[name].early or self.sense.park

    def _answer(self, v, step, opened):
        text = v.text
        move, ack, heard_as = self._listen(v, step, opened)
        move = self._ends_there(move, v, opened)
        if self._hesitates(move):
            return self._revisit(), self.ui_stage(), "hesitates"
        earlier = self._earlier(step)
        self.state = move.state
        # an answer with a question in it: the question gets an answer when the facts have one, else
        # nothing ("what's next?" needs none). After the judge: a failed AI line can't cost it.
        heard = self._side(v, opened) if v.side else (self._answer_uncovered(text, opened) if v.asking else "")
        leads = (*(step.reask or self.method.reask), *self.sense.yes_no_reask)  # "No rush" in front says they weren't heard; a route's ack says they were
        asked_again = move.state.step == step.id and (not move.ack or move.ack in leads)
        meant = self._meaning(text) if asked_again and not heard else ""
        if meant:
            move = replace(move, ack="")  # "That's a fair worry." in place of "No rush"
        body = self._render(move)  # first: the question may quote them, and then the AI line may not
        acked = move.ack and self._filler.fill(move.ack, move.state.slots) is not None  # "{months} months..." needs a number
        if meant:  # asked again: "scared of losing money" to "how long?" is still heard, never quoted
            return tone.join(meant, body), move.ui_stage, heard_as
        if heard or acked or move.state.step == step.id:
            return (f"{heard} {body}" if heard else body), move.ui_stage, heard_as
        line, own = self._react(text, step, ack, earlier, opened)
        if not line:
            return body, move.ui_stage, heard_as
        return (tone.join(line, body) if own else f"{line} {body}"), move.ui_stage, heard_as

    def _react(self, text, step, ack, earlier, opened):
        """What shows their answer was heard: (line, own bubble). A meaning line first (no AI, and no quoting
        them); else the AI's "I heard you" line, which says their words back, so only when the echo budget
        allows it; else nothing."""
        line = self._meaning(text)
        if line:
            return line, True
        if not self._echo.may_quote(self._turn, self.state, (), False):
            return "", False
        if ack is None:
            ack = self._voice.ack(text, step.say_plain or step.say, earlier, opened)
        if ack and (words := self._echo.quoted(ack, text)):
            quote = (" ".join(words),)
            if not self._echo.may_quote(self._turn, self.state, quote, False):
                return "", False  # a whole sentence of theirs, or a phrase said too often
            Echo.said(self._turn, quote)
        return ack, False

    def _meaning(self, text):
        """The meaning bank's line for the reply, each once a call; "" when it means none."""
        line = self._meanings.line(text, self.state.meant + self._turn.meant)
        if line:
            self._turn.meant += (line,)
        return line

    def _earlier(self, step):
        """Their answers to the other steps: what an AI line may link to."""
        return {k: v for k, v in self.state.slots.items() if k != step.capture}

    def _go(self, move):
        """Take a move as it is: no "I heard you" line in front of it."""
        self.state = move.state
        return self._render(move), move.ui_stage

    def _sense(self, said):
        """An everyday interruption: its reply, then what its `after` says."""
        if said.after == "wait":
            self.state = replace(self.state, waiting=True)  # "brb" twice: never the same words twice in a row
            again = said.reply == self.state.last and self.sense.wait_again
            return (self.sense.wait_again if again else said.reply), self.ui_stage()
        if said.after == "follow_up":  # "bye": book the follow-up, never carry on as if they stayed
            text, stage = self._go(jump(self.method, self.state, self.method.follow_up))
            return f"{said.reply} {text}".strip(), stage
        if said.after == "ask":  # said again straight after ("what about you?" twice): the reminder, not the same line
            return self._then_ask(self._unless_just_said(said.reply)), self.ui_stage()
        return self._carry_on(said.reply, rephrase=said.after == "rephrase")

    def _carry_on(self, lead, rephrase=False, stay=False):
        """`lead`, then the step in other words; a step with no other words moves on instead (without
        taking the reply as its answer), so the same line is never said twice in a row. `stay`: a step with
        other words is moved on from only once asked once more than usual (`engine._ask_again`). A rephrase
        that moved on drops its lead: "let me put it another way" in front of a new question is untrue; one
        back on the step's own question (no other words left) says `same_words` instead."""
        step = self.state.step
        move = carry_on(self.method, self.state, rephrase, stay, self.cfg["misses"])
        text, stage = self._go(move)
        if rephrase and self.state.step != step:
            lead = ""
        elif rephrase and move.say == question_of(self.state.opened or self.method.steps[step].say):
            lead = self.sense.same_words or lead  # no other words left: never promise them
        return f"{lead} {text}".strip(), stage

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
        needed = self._ear.shaped(text, step)
        ruled = next((r.label for r in step.listen if r.says(text)), None)
        if ruled and not empty:
            label = ruled  # by rule, before meaning: round 43, "6 weeks" was unclear ("so many nights, months and years")
        elif labels and not empty:  # a shrug takes no answer's route: "ok" to "Where are you at with it?" is no yes
            floors = {r.label: r.min_score for r in step.listen if r.label}
            found = self._listener.answer(text, labels, list(self.sense.unclear), floors)
            restates = {r.label for r in step.listen if r.restates}
            rest = self._after_restated(text, {k: labels[k] for k in restates}) if found.label in restates else ""
            if rest:  # "i want to make money online so i can quit my job": the question said back, then the answer
                after = self._listener.answer(rest, labels, list(self.sense.unclear), floors)
                if after.label and after.label not in restates and not after.close:
                    text, found = rest, after
            climbs = next((r.climbs_to for r in step.listen if r.label == found.label), ())  # torn with the next rung too
            rest = self._after_restated(text, {found.label: labels[found.label]}) if climbs else ""
            up = self._listener.answer(rest, labels, list(self.sense.unclear), floors) if rest else None
            if up and up.label in climbs and not up.close and up.score >= self.cfg["climb_min_score"]:  # round 100: "more money so I can stop worrying about
                found = up  # bills" is already the next rung; the whole reply is still kept
            label, near = found.label, found.candidates
            if found.close:
                pick = self._voice.judge(text, {c: labels[c] for c in near}) if near else VAGUE
                label = None if pick == VAGUE else pick
                if found.label and not label and step.unsure and all(r.then != step.id for r in step.listen if r.label in found.torn):
                    label = step.unsure  # every meaning it is torn between is a real answer: take the step's safe one, don't ask again
        # round 109: a step with an exit beside its "any" route (09's "I don't have any") still hears the rest
        takes_any = not labels or any(r.label == ANY for r in step.listen)
        if (not label and takes_any and needed and self.cfg["listen"] and step.capture
                and not (empty and not asks_left(self.method, self.state, self.cfg["misses"]))):
            concept = f"{step.name}: {step.note}" if step.note else step.name  # the AI hears for it
            heard = self._voice.listen(text, concept, self._asked_text(), self._earlier(step), opened)
            if heard is not None:
                missed = not heard.answered
                empty, line, ack = empty or missed, heard.probe, heard.ack
        # "I don't know where to start" to "how much a month?": no figure in it. A route that doesn't keep the
        # reply ("I tried dropshipping and it failed" to "how long?") needs none: it isn't taken as the answer.
        short = not needed and (not label or any(r.keep for r in step.listen if r.label == label))
        if short:
            empty, missed = True, True
        clarified = False
        if step.capture and not line and not self.state.said and not short:  # their words asked about once a step, never twice
            line = self._shrugs.ask_meaning(text, self._asked_text(), empty, v.ahead is not None,
                                            self.state.slots.values(), self.state.clarified)  # said only if asked again
            clarified = bool(line)
        detail = ""
        if missed:
            detail = "misses"
        elif v.kind == "answer":
            detail = f"answer:{label}" if label else ("answer:any" if not labels else "answer:unclear")
        move = advance(self.method, self.state, label, text, empty, line, self.cfg["misses"])
        if clarified and line in move.state.said:
            move = replace(move, state=replace(move.state, clarified=move.state.clarified + 1))
        return self._closed_lead(move), ack, detail

    def _ends_there(self, move, v, opened):
        """The step this reply led to, when the same reply already ends the call there: "yes, debit" to
        "jumping in?" goes to the payment question, and "debit" answers it (round 27 callers: "Credit or
        debit?" after "debit"). Only an ending (a step with no routes, never the follow-up) is taken: "how
        do I pay?" still gets the question."""
        to = self.method.steps[move.state.step]
        if to.id == self.state.step or not any(self._ends(r.then) for r in to.listen):
            return move
        here, self.state = self.state, move.state
        try:
            then, _, _ = self._listen(replace(v, ahead=None), to, opened)
        finally:
            self.state = here
        return then if self._ends(then.state.step) and then.state.step != to.id else move

    def _ends(self, step_id):
        return not self.method.steps[step_id].routes and step_id != self.method.follow_up

    def _after_restated(self, text, said_back):
        """What follows the part of a long reply that only says the question back (`said_back`: those routes'
        examples): "Well it's a long story. ... I want something online that pays the bills so I can cut down
        my hours" -> "so I can cut down my hours". "" when that part ends the reply or it has one part."""
        parts = clauses(text, self._listener.breaks)
        if len(parts) < 2:
            return ""
        scores = [self._listener.match(p, said_back, by_clause=False).score for p in parts]
        return after(text, parts[scores.index(max(scores))])

    def _closed_lead(self, move):
        """A yes-or-no question asked again gets a yes-or-no lead, in the same turn: "No rush, even a rough
        idea helps." in front of "Would that work for you?" asks for a guess nobody needs."""
        leads, closed = self.method.reask, self.sense.yes_no_reask
        if move.ack not in leads or not self._ear._yes_or_no(move.state):
            return move
        turn = leads.index(move.ack)
        return replace(move, ack=closed[turn] if turn < len(closed) else "")

    def _asked_text(self):
        """The step's question as it was just asked, blanks filled, tone marks off."""
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
        said again: a fact answered at a statement step said the statement twice. Said again once: a second
        side reply in a row gets the step in other words, or moves on (`_carry_on`), never the same line."""
        self._turn.side = True
        if self.state.repeated:
            return self._carry_on(lead.strip(), stay=True)[0]
        say, say_plain = asked_line(self.method, self.state)  # the words last used, not always the first
        question = self._line(self.method.steps[self.state.step], say, "", say_plain, self.state.slots,
                              theirs=bool(self.state.asked))
        if "?" not in question:
            question = ""
        else:  # the question said again spends an ask: never a 4th time after two shrugs
            self.state = replace(self.state, resaid=self.state.resaid + 1)
        return f"{lead.strip()} {question.strip()}".strip()

    def _render(self, move):
        """The message: any run_on steps, then the step's line."""
        said = []
        for step_id in move.lead:
            lead = self.method.steps[step_id]
            said.append(self._line(lead, lead.say, "", lead.say_plain, move.state.slots))
        step = self.method.steps[move.state.step]
        said.append(self._line(step, move.say, move.ack, step.say_plain, move.state.slots, move.theirs))
        return " ".join(said)

    def _line(self, step, say, ack, say_plain, slots, theirs=False):
        """One line as said, within the echo budget (echo.py): their words where it allows, else the plain
        line. `theirs`: the line was made from their reply ("What do you mean by ...?", an AI probe)."""
        phrases = self._filler.echoes(say, slots) + self._filler.echoes(ack, slots)
        circular = step.plain_if and any(re.search(step.plain_if, p, re.IGNORECASE) for p in phrases)
        if phrases and (circular or not self._echo.may_quote(self._turn, self.state, phrases, step.moment)):
            slots, phrases = {k: v for k, v in slots.items() if k not in self._filler.echo}, []
        if phrases:
            Echo.said(self._turn, phrases)
        line = self._filler.render(say, ack, say_plain, slots)
        if theirs:
            self._echo.count(self._turn, line)
        return line
