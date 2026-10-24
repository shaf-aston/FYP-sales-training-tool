"""Pure script logic: given where we are and what the prospect meant, pick the next line."""

import re
from dataclasses import dataclass, field, replace

from core.script_engine.method import ANY


@dataclass(frozen=True)
class ScriptState:
    step: str
    slots: dict = field(default_factory=dict)
    raised: tuple = ()  # objections handled after the price, oldest first
    asks: int = 0       # times the current step has been asked again
    asked: str = ""     # the AI's own words the step was last asked in, if any (see `asked_line`)
    said: tuple = ()    # every such line asked on the current step, so none is asked twice
    parked: tuple = ()  # objections raised before the price, oldest first; raised again at the revisit step
    waiting: bool = False  # their last reply was a `wait` sense ("brb"): the next may be "I'm back"
    quoted: bool = False   # the last message said their words back (the echo budget, echo.py)
    echoed: tuple = ()     # their phrases said back this call, once per time said
    meant: tuple = ()      # meaning lines said this call


@dataclass(frozen=True)
class Move:
    say: str            # still contains {blanks}; fill.py resolves them
    state: ScriptState
    ui_stage: str
    ack: str = ""       # short fixed lead-in from the route taken
    lead: tuple = ()    # run_on step ids said first, in order
    theirs: bool = False  # `say` was made from their reply (a clarifying question, an AI probe)


def _speak(method, state):
    """Walk past silent and already-answered steps, say any run_on steps, then say the step we land on."""
    step, lead = method.steps[state.step], ()
    while not step.say or step.run_on or _answered(step, state):
        if step.say and not _answered(step, state):
            lead += (step.id,)
        state = replace(state, step=_route(step, ANY).then)
        step = method.steps[state.step]
    return Move(step.say, replace(state, asks=0, asked="", said=()), step.ui_stage, lead=lead)


def _answered(step, state):
    """They gave this step's answer before it was asked (see `hear_ahead`)."""
    return bool(step.answered_by) and step.capture in state.slots


def _route(step, label):
    return next((r for r in step.listen if r.label == label), None)


def start(method):
    return _speak(method, ScriptState(step=method.first))


def advance(method, state, label, reply="", empty=False, line="", misses=1):
    """label = the recognised route label or None. Unmatched reply asks the step again.
    empty = the reply says nothing ("ok", "idk") or misses what the step is after: an open question, or a
    step with answers of its own that heard none ("um" to "the money, your partner, or something else?"), is
    asked again `misses` times (in `line` when given, else its next probe), then the call moves on without
    saving the reply as their answer. `line` is used only when the step is asked again."""
    step = method.steps[state.step]
    if empty and (step.capture or not label and any(r.label != ANY for r in step.listen)):
        if asks_left(method, state, misses):
            return _ask_again(method, state, step, line=line, misses=misses)
        reply = ""
    route = _route(step, label) if label else None
    route = route or _route(step, ANY)
    if route is None:
        return _ask_again(method, state, step, line=line, misses=misses)
    if step.capture and reply and route.keep:
        state = replace(state, slots={**state.slots, step.capture: reply})
    if route.then == state.step:
        return _ask_again(method, state, step, route.ack, line=line, misses=misses)
    return _take(method, state, route)


def _take(method, state, route):
    return replace(_speak(method, replace(state, step=route.then)), ack=route.ack)


def ask_again(method, state):
    """The current step in other words (they asked what it meant). No `reask` lead: the caller's own lead
    (the sense's reply) goes in front."""
    return _ask_again(method, state, method.steps[state.step], lead=False)


def _limit(step, misses):
    """How many times the step is asked again: `misses` for a step that captures an answer, else once per probe."""
    return misses if step.capture and misses else len(step.probes or (step.say,))


def asks_left(method, state, misses):
    """The current step may still be asked again before it moves on."""
    return state.asks < _limit(method.steps[state.step], misses)


def _ask_again(method, state, step, ack="", line="", misses=0, lead=True):
    """A person rephrases rather than repeating themselves, and moves on rather than asking forever.
    `line`: the words to ask in (the AI's, or a clarifying question), dropped if already said on this step;
    else the step's next probe; once those run out, its last question again behind a `reask` lead (each
    once, then none), so no line is said twice. Asked `_limit` times, then `stuck`. A step that asks nothing (a closing line, a
    statement) is said again plain: "no rush" in front of it answers a question nobody asked."""
    if step.stuck and state.asks >= _limit(step, misses):
        return _take(method, state, step.stuck)
    if line.strip().lower() in {s.strip().lower() for s in state.said}:
        line = ""  # never the same words twice on one step
    used = state.asks - len(state.said)  # times asked in the script's words: a probe is never skipped
    if line:
        said = line
    elif used < len(step.probes):
        said = step.probes[used]
    else:
        said = step.probes[-1] if step.probes else _question(step.say)
        turn = used - len(step.probes)  # each lead once a step: a third "No rush" sounds like a loop
        if lead and turn < len(method.reask) and not ack and (step.probes or "?" in step.say):
            ack = method.reask[turn]
    state = replace(state, asks=state.asks + 1, asked=line, said=state.said + (line,) if line else state.said)
    return Move(said, state, step.ui_stage, ack=ack, theirs=bool(line))


def _question(say):
    """The question in a line, without the talk before it: asked again, the talk is not said twice."""
    asks = [s for s in re.split(r"(?<=[.!?])\s+", say) if s.endswith("?")]
    return asks[-1] if asks else say


def asked_line(method, state):
    """The words the current step was last asked in: (line, plain line). After an ask-again that is
    the probe said last, so a side question doesn't rewind to the first wording."""
    step = method.steps[state.step]
    if state.asked:
        return state.asked, ""
    used = state.asks - len(state.said)
    if used == 0 or not step.probes:
        return step.say, step.say_plain
    return step.probes[min(used - 1, len(step.probes) - 1)], ""


def move_on(method, state):
    """Leave the step without taking their reply as its answer (they pushed back on the question).
    No slot is saved and the route's ack is not said: it may build on an answer they never gave."""
    step = method.steps[state.step]
    route = _route(step, ANY) or step.stuck
    if route is None:
        return _ask_again(method, state, step)
    return _speak(method, replace(state, step=route.then))


def jump(method, state, step_id):
    """Go straight to `step_id`. They told us where they are, so parked worries are dropped."""
    return _speak(method, replace(state, step=step_id, parked=()))


def hear_ahead(method, state, text):
    """Keep an answer to a later step given early ("I want 5k a month"); that step is then skipped."""
    order = list(method.steps)
    slots = dict(state.slots)
    for step_id in order[order.index(state.step) + 1:]:
        step = method.steps[step_id]
        if step.answered_by and step.capture not in slots:
            found = re.search(step.answered_by, text, re.IGNORECASE)
            if found:
                slots[step.capture] = found.group("answer").strip()
    return state if slots == state.slots else replace(state, slots=slots)


def price_open(method, step_id):
    """True once the script has reached the step where the price may be said."""
    order = list(method.steps)
    return order.index(step_id) >= order.index(method.price_step)


def ready_open(method, step_id):
    """True while a keen prospect may skip ahead: before the method's `ready.until` step."""
    order = list(method.steps)
    return method.ready is not None and order.index(step_id) < order.index(method.ready.until)


def object_to(method, state, name, entries):
    """Handle an objection by its matrix branch. Past `entries` objections in one call they are
    smokescreens: book the follow-up instead."""
    to = method.follow_up if len(state.raised) >= entries else method.objections[name].enter
    parked = tuple(p for p in state.parked if p != name)
    return _speak(method, replace(state, step=to, raised=(*state.raised, name), parked=parked))


def park(state, name):
    """Remember an objection raised before the price, once."""
    return state if name in state.parked else replace(state, parked=(*state.parked, name))
