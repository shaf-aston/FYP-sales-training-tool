"""Pure script logic: given where we are and what the prospect meant, pick the next line."""

import re
from dataclasses import dataclass, field, replace

from core.script_engine.method import ANY


@dataclass(frozen=True)
class ScriptState:
    step: str
    slots: dict = field(default_factory=dict)
    objection_counts: dict = field(default_factory=dict)
    last_point: str = ""
    play: str = ""      # objection whose loop/direct line was just asked; the next reply answers it
    asks: int = 0       # times the current step has been asked again
    parked: tuple = ()  # objections raised before the price, oldest first; raised again at the revisit step


@dataclass(frozen=True)
class Move:
    say: str            # still contains {blanks}; fill.py resolves them
    state: ScriptState
    ui_stage: str
    done: bool = False  # landed on a step with nothing left to listen for
    ack: str = ""       # short fixed lead-in from the route taken
    lead: tuple = ()    # run_on step ids said first, in order

    @property
    def text_template(self):
        return f"{self.ack} {self.say}".strip()


def _speak(method, state):
    """Walk past silent and already-answered steps, say any run_on steps, then say the step we land on."""
    step, lead = method.steps[state.step], ()
    while not step.say or step.run_on or _answered(step, state):
        if step.say and not _answered(step, state):
            lead += (step.id,)
        state = replace(state, step=_route(step, ANY).then)
        step = method.steps[state.step]
    return Move(step.say, replace(state, asks=0), step.ui_stage, not step.listen, lead=lead)


def _answered(step, state):
    """They gave this step's answer before it was asked (see `hear_ahead`)."""
    return bool(step.answered_by) and step.capture in state.slots


def _route(step, signal):
    return next((r for r in step.listen if r.signal == signal), None)


def start(method):
    return _speak(method, ScriptState(step=method.first))


def advance(method, state, signal, reply="", empty=False):
    """signal = recognised label or None. Unmatched reply asks the step again.
    empty = the reply says nothing ("ok", "sure"): an open question is asked once more, then the
    call moves on without saving it as their answer."""
    step = method.steps[state.step]
    if empty and step.capture:
        if state.asks < 1:
            return _ask_again(method, state, step)
        reply = ""
    route = _route(step, signal) if signal else None
    route = route or _route(step, ANY)
    if route is None:
        return _ask_again(method, state, step)
    if step.capture and reply:
        state = replace(state, slots={**state.slots, step.capture: reply}, last_point=reply)
    if route.then == state.step:
        return _ask_again(method, state, step, route.ack)
    return _take(method, state, route)


def _take(method, state, route):
    return replace(_speak(method, replace(state, step=route.then)), ack=route.ack)


def ask_again(method, state):
    """The current step in other words (they asked what it meant)."""
    return _ask_again(method, state, method.steps[state.step])


def _ask_again(method, state, step, ack=""):
    """A person rephrases rather than repeating themselves, and moves on rather than asking forever."""
    lines = step.probes or (step.say,)
    if step.stuck and state.asks >= len(lines):
        return _take(method, state, step.stuck)
    line = lines[min(state.asks, len(lines) - 1)]
    return Move(line, replace(state, asks=state.asks + 1), step.ui_stage, not step.listen, ack=ack)


def asked_line(method, state):
    """The words the current step was last asked in: (line, plain line). After an ask-again that is
    the probe said last, so a side question doesn't rewind to the first wording."""
    step = method.steps[state.step]
    if state.asks == 0 or not step.probes:
        return step.say, step.say_plain
    return step.probes[min(state.asks - 1, len(step.probes) - 1)], ""


def move_on(method, state):
    """Leave the step without taking their reply as its answer (they pushed back on the question).
    No slot is saved and the route's ack is not said: it may build on an answer they never gave."""
    step = method.steps[state.step]
    route = _route(step, ANY) or step.stuck
    if route is None:
        return _ask_again(method, state, step)
    return _speak(method, replace(state, step=route.then))


def jump(method, state, step_id):
    """Go straight to `step_id`. They told us where they are, so an open play and parked worries are dropped."""
    return _speak(method, replace(state, step=step_id, play="", parked=()))


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
    """True while a keen buyer may skip ahead: before the method's `ready.until` step."""
    order = list(method.steps)
    return method.ready is not None and order.index(step_id) < order.index(method.ready.until)


def object_to(method, state, name, loops):
    """Answer an objection: loop lines first, then the direct line, then the follow-up."""
    objection = method.objections[name]
    seen = state.objection_counts.get(name, 0)
    if seen < loops:
        line = objection.loop[min(seen, len(objection.loop) - 1)]
    elif seen == loops:
        line = objection.direct
    else:
        line = method.follow_up
    counts = {**state.objection_counts, name: seen + 1}
    step = method.steps[state.step]
    play = name if seen <= loops else ""
    parked = tuple(p for p in state.parked if p != name)
    return Move(line, replace(state, objection_counts=counts, play=play, parked=parked), step.ui_stage, seen > loops)


def park(state, name):
    """Remember an objection raised before the price, once."""
    return state if name in state.parked else replace(state, parked=(*state.parked, name))
