"""Pure script logic: given where we are and what the prospect meant, pick the next line."""

from dataclasses import dataclass, field, replace

from core.script_engine.method import ANY


@dataclass(frozen=True)
class ScriptState:
    step: str
    slots: dict = field(default_factory=dict)
    objection_counts: dict = field(default_factory=dict)
    last_point: str = ""
    play: str = ""      # objection whose loop/direct line was just asked; the next reply answers it


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
    """Walk past silent steps, say any run_on steps, then say the step we land on."""
    step, lead = method.steps[state.step], ()
    while not step.say or step.run_on:
        if step.say:
            lead += (step.id,)
        state = replace(state, step=_route(step, ANY).then)
        step = method.steps[state.step]
    return Move(step.say, state, step.ui_stage, not step.listen, lead=lead)


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
    if route.then == state.step and step.probe:
        # asked again: a person rephrases rather than repeating themselves word for word
        return Move(step.probe, replace(state, slots=slots, last_point=last_point), step.ui_stage,
                    ack=route.ack)
    moved = _speak(method, replace(state, step=route.then, slots=slots, last_point=last_point))
    return replace(moved, ack=route.ack)


def price_open(method, step_id):
    """True once the script has reached the step where the price may be said."""
    order = list(method.steps)
    return order.index(step_id) >= order.index(method.price_step)


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
    return Move(line, replace(state, objection_counts=counts, play=play), step.ui_stage, seen > loops)
