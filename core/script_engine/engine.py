"""Pure script logic: given where we are and what the prospect meant, pick the next line."""

from dataclasses import dataclass, field, replace

from core.script_engine.method import ANY


@dataclass(frozen=True)
class ScriptState:
    step: str
    slots: dict = field(default_factory=dict)
    objection_counts: dict = field(default_factory=dict)
    last_point: str = ""


@dataclass(frozen=True)
class Move:
    text_template: str  # still contains {blanks}; fill.py resolves them
    state: ScriptState
    ui_stage: str
    done: bool = False  # landed on a step with nothing left to listen for


def _speak(method, state):
    """Walk past silent steps, then say the step we land on."""
    step = method.steps[state.step]
    while not step.say:
        state = replace(state, step=_route(step, ANY).then)
        step = method.steps[state.step]
    return Move(step.say, state, step.ui_stage, not step.listen)


def _route(step, signal):
    return next((r for r in step.listen if r.signal == signal), None)


def start(method):
    return _speak(method, ScriptState(step=method.first))


def advance(method, state, signal, reply=""):
    """signal = recognised label or None. Unmatched reply repeats the step as a probe."""
    step = method.steps[state.step]
    route = _route(step, signal) if signal else None
    route = route or _route(step, ANY)
    if route is None:
        return Move(step.probe or step.say, state, step.ui_stage, not step.listen)
    slots, last_point = state.slots, state.last_point
    if step.capture and reply:
        slots = {**slots, step.capture: reply}
        last_point = reply
    moved = _speak(method, replace(state, step=route.then, slots=slots, last_point=last_point))
    if route.ack:
        return replace(moved, text_template=f"{route.ack} {moved.text_template}")
    return moved
