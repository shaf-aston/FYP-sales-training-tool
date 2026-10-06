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
    asks: int = 0       # times the current step has been asked again


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
    return Move(step.say, replace(state, asks=0), step.ui_stage, not step.listen, lead=lead)


def _route(step, signal):
    return next((r for r in step.listen if r.signal == signal), None)


def start(method):
    return _speak(method, ScriptState(step=method.first))


def advance(method, state, signal, reply=""):
    """signal = recognised label or None. Unmatched reply asks the step again."""
    step = method.steps[state.step]
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


def _ask_again(method, state, step, ack=""):
    """A person rephrases rather than repeating themselves, and moves on rather than asking forever."""
    lines = step.probes or (step.say,)
    if step.stuck and state.asks >= len(lines):
        return _take(method, state, step.stuck)
    line = lines[min(state.asks, len(lines) - 1)]
    return Move(line, replace(state, asks=state.asks + 1), step.ui_stage, not step.listen, ack=ack)


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
