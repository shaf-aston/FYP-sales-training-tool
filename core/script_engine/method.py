"""Load and validate sales-method and offer YAML into frozen dataclasses."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from core.loader import CONFIG_DIR
from core.enums import Stage

ANY = "any"  # listen route with no examples: taken for any reply


@dataclass(frozen=True)
class Route:
    signal: str
    examples: tuple
    then: str
    ack: str = ""


@dataclass(frozen=True)
class Step:
    id: str
    ui_stage: str
    say: str            # empty = silent step, never spoken
    say_plain: str
    capture: str        # slot name that stores the prospect's reply
    probe: str          # asked when no route matched; empty = repeat `say`
    draft: bool         # some line here is not verbatim from the source
    listen: tuple       # of Route
    run_on: bool = False  # said, then straight on to the next step without waiting for a reply
    name: str = ""      # the step's name in the source script, shown to the trainee
    note: str = ""      # the source's "listen for" note: what the trainee should notice next
    doubts_answer: bool = False  # the question asks what holds them back: "money's tight" is the answer


@dataclass(frozen=True)
class Objection:
    name: str
    examples: tuple
    loop: tuple
    direct: str
    draft: bool
    normalise: str = ""  # said once they answer a loop line, before the step's question again


@dataclass(frozen=True)
class Method:
    name: str
    first: str
    steps: dict         # in script order
    objections: dict
    price_step: str     # the price may be said from this step on
    follow_up: str      # said once an objection has been looped and met directly


@dataclass(frozen=True)
class Fact:
    topic: str
    examples: tuple
    answer: str
    late_answer: str    # used once the price step is reached; empty = same answer
    draft: bool


@dataclass(frozen=True)
class Offer:
    name: str
    months: int
    price: str
    pillars: tuple
    context: str
    facts: dict


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects a repeated key instead of silently keeping the last."""

    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(k, deep=True) for k, _ in node.value]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ValueError(f"duplicate keys in YAML: {sorted(map(str, dupes))}")
        return super().construct_mapping(node, deep)


@dataclass(frozen=True)
class Interruption:
    name: str
    examples: tuple
    reply: str
    draft: bool
    wait: bool = False  # say the reply and wait; don't ask the question again yet
    after_wait: bool = False  # only makes sense right after a `wait` reply ("ok, I'm back")


@dataclass(frozen=True)
class CommonSense:
    bring_back: str
    park: str
    interruptions: dict


def _read(directory, name):
    path = Path(directory) / f"{name}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=_StrictLoader)


def _route(step_id, signal, data):
    if not isinstance(signal, str):
        raise TypeError(f"step {step_id}: route name {signal!r} is not text (quote yes/no)")
    examples = tuple(data.get("examples") or ())
    if signal == ANY and examples:
        raise ValueError(f"step {step_id}: '{ANY}' route takes no examples")
    if signal != ANY and not examples:
        raise ValueError(f"step {step_id}: route '{signal}' needs examples")
    return Route(signal, examples, str(data["then"]), data.get("ack", ""))


def _step(step_id, data):
    stage = data.get("ui_stage")
    if stage not in {s.value for s in Stage}:
        raise ValueError(f"step {step_id}: unknown ui_stage {stage!r}")
    listen = tuple(_route(step_id, k, v) for k, v in (data.get("listen") or {}).items())
    if not data.get("say") and not any(r.signal == ANY for r in listen):
        raise ValueError(f"step {step_id}: silent step needs an '{ANY}' route")
    if data.get("run_on") and not any(r.signal == ANY for r in listen):
        raise ValueError(f"step {step_id}: run_on step needs an '{ANY}' route")
    return Step(
        step_id, stage, data.get("say", ""), data.get("say_plain", ""),
        data.get("capture", ""), data.get("probe", ""),
        bool(data.get("draft")), listen, bool(data.get("run_on")),
        data.get("name", ""), data.get("note", ""), bool(data.get("doubts_answer")),
    )


def _objection(name, data):
    return Objection(
        name, tuple(data["examples"]), tuple(data["loop"]),
        data["direct"], bool(data.get("draft")), data.get("normalise", ""),
    )


def parse_method(name, data):
    """Build a Method from parsed YAML. Fails loud on a broken script graph."""
    steps = {str(k): _step(str(k), v) for k, v in data["steps"].items()}
    first = str(data.get("first", ""))
    if first not in steps:
        raise ValueError(f"method {name}: first step {first!r} not defined")
    for step in steps.values():
        for route in step.listen:
            if route.then not in steps:
                raise ValueError(f"step {step.id}: unknown then {route.then!r}")
    objections = {k: _objection(k, v) for k, v in (data.get("objections") or {}).items()}
    price_step = str(data.get("price_step", ""))
    if price_step not in steps:
        raise ValueError(f"method {name}: price_step {price_step!r} not defined")
    follow_up = (data.get("follow_up") or {}).get("say", "")
    return Method(name, first, steps, objections, price_step, follow_up)


def parse_offer(name, data):
    facts = {
        k: Fact(
            k, tuple(v.get("examples") or ()), v["answer"],
            v.get("late_answer", ""), bool(v.get("draft")),
        )
        for k, v in (data.get("facts") or {}).items()
    }
    return Offer(
        name, int(data["months"]), str(data["price"]),
        tuple(data["pillars"]), data["context"], facts,
    )


def parse_common_sense(data):
    items = {
        k: Interruption(k, tuple(v["examples"]), v["reply"], bool(v.get("draft")),
                        bool(v.get("wait")), bool(v.get("after_wait")))
        for k, v in data["interruptions"].items()
    }
    return CommonSense(data["bring_back"], data["park"], items)


def load_method(name, directory=CONFIG_DIR / "methods"):
    return parse_method(name, _read(directory, name))


def load_offer(name, directory=CONFIG_DIR / "offers"):
    return parse_offer(name, _read(directory, name))


def load_common_sense(name="common_sense", directory=CONFIG_DIR / "script"):
    return parse_common_sense(_read(directory, name))
