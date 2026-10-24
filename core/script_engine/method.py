"""Load and validate sales-method and offer YAML into frozen dataclasses."""

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from core.enums import Stage
from core.loader import CONFIG_DIR
from core.script_engine.tone import stresses

BLANK = re.compile(r"\{(\w+)")  # the name of each {blank} in a line
ANY = "any"  # listen route with no examples: taken for any reply
# What happens after an interruption's reply: ask the step again (same words), wait for them to come
# back, ask it in other words, or (a step with no other words) move on to the next step.
AFTER = ("ask", "wait", "rephrase", "rephrase_else_move_on")


@dataclass(frozen=True)
class Route:
    label: str          # what the reply means; matched against `examples` (ANY: every reply)
    examples: tuple
    then: str
    ack: str = ""
    keep: bool = True   # false = the reply is not kept as the step's answer (a vague one restates the question)
    min_score: float = 0.0  # a match must score at least this to take the route; under it, the reply is heard as unmatched


@dataclass(frozen=True)
class Step:
    id: str
    ui_stage: str
    say: str            # empty = silent step, never spoken
    say_plain: str
    capture: str        # slot name that stores the prospect's reply
    probes: tuple       # asked in turn when no route moves on, before `stuck`; then a `reask` lead + the last
    listen: tuple       # of Route
    run_on: bool = False  # said, then straight on to the next step without waiting for a reply
    name: str = ""      # the step's name in the source script, shown to the learner
    note: str = ""      # the source's "listen for" note: what the learner should notice next
    doubts_answer: bool = False  # the question asks what holds them back: "money's tight" is the answer
    stuck: Route = None  # taken once the step has been asked again enough; every step with no `any` route has one
    answered_by: str = ""  # regex with an `answer` group: the step's answer given early; the step is then skipped
    echo: bool = False  # their answer may be said back in their own words in a later line's {blank}
    unsure: str = ""    # a close call nobody settles, between answers that all move on, is heard as this one
    moment: bool = False  # one of the call's few moments for their exact words (see echo.py); elsewhere a short term at most

    @property
    def routes(self):
        return self.listen + ((self.stuck,) if self.stuck else ())


@dataclass(frozen=True)
class Objection:
    name: str
    examples: tuple
    enter: str           # after the price: the matrix step its branch starts at
    early: str = ""      # before the price: a short honest answer instead of `park`; may be raised while asking


@dataclass(frozen=True)
class Ready:
    """A keen prospect says they're in before the pitch: skip to `then` instead of making them sit through it."""
    examples: tuple
    then: str           # the step the call jumps to
    until: str          # only before this step; from here on the script itself is closing
    min_score: float    # a match must score at least this on every step ("I'm in sales" must not jump)


@dataclass(frozen=True)
class Method:
    name: str
    first: str
    steps: dict         # in script order
    objections: dict
    price_step: str     # the price may be said from this step on
    follow_up: str      # step the call ends on once too many objections came up (a smokescreen)
    revisit_step: str = ""  # an objection parked before the price is raised again when they hesitate here
    ready: Ready = None     # keen prospect shortcut; none = every prospect hears the whole script
    reask: tuple = ()       # leads said before a question asked again once its probes ran out, in turn


@dataclass(frozen=True)
class Fact:
    examples: tuple
    answer: str
    late_answer: str    # used once the price step is reached; empty = same answer


@dataclass(frozen=True)
class Offer:
    name: str
    months: int
    price: str
    pillars: tuple
    facts: dict
    about: str = ""     # what the AI may say when no fact covers a question; empty = never answer from it
    about_after_price: str = ""  # added to `about` from the price step on


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
    after: str = "ask"  # one of AFTER: what follows the reply
    after_wait: bool = False  # only makes sense right after a `wait` reply ("ok, I'm back")
    min_score: float = 0.0  # a match must score at least this on every step (words that are often answers too)


@dataclass(frozen=True)
class CommonSense:
    park: str
    revisit: str        # lead-in when a parked objection is raised again
    interruptions: dict
    nudge: str = ""     # said when a reply only nudges ("what's next?"), before carrying on
    nudges: tuple = ()  # phrases that nudge, cut off the end of a reply
    unclear: tuple = ()  # replies that give nothing to an open question ("dunno man", "stuff I guess")
    unclear_min_score: float = 1.0  # a reply counts as unclear when it matches `unclear` at least this well
    ask_meaning: str = ""  # asks what they meant by their own words ({said}); empty = never asked


@dataclass(frozen=True)
class Meaning:
    """What an answer means, beyond its words ("my mum's relying on me": family duty), and lines that say so."""
    name: str
    examples: tuple
    lines: tuple        # said in turn, each once a call; none of them asks


@dataclass(frozen=True)
class Meanings:
    items: dict
    min_score: float    # an answer means one only when it matches this well
    min_words: int = 2  # and says this many words that carry meaning: "debt" or "for my mum" means none


def _read(directory, name):
    path = Path(directory) / f"{name}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=_StrictLoader)


def _route(step_id, label, data):
    if not isinstance(label, str):
        raise TypeError(f"step {step_id}: route name {label!r} is not text (quote yes/no)")
    examples = tuple(data.get("examples") or ())
    if label == ANY and examples:
        raise ValueError(f"step {step_id}: '{ANY}' route takes no examples")
    if label != ANY and not examples:
        raise ValueError(f"step {step_id}: route '{label}' needs examples")
    if label == ANY and "min_score" in data:
        raise ValueError(f"step {step_id}: '{ANY}' route takes no min_score")
    floor = _score(f"step {step_id} route {label}", data["min_score"]) if "min_score" in data else 0.0
    return Route(label, examples, str(data["then"]), data.get("ack", ""), data.get("keep", True) is not False, floor)


def _step(step_id, data):
    stage = data.get("ui_stage")
    if stage not in {s.value for s in Stage}:
        raise ValueError(f"step {step_id}: unknown ui_stage {stage!r}")
    listen = tuple(_route(step_id, k, v) for k, v in (data.get("listen") or {}).items())
    probes = data.get("probe") or ()
    probes = (probes,) if isinstance(probes, str) else tuple(probes)
    stuck = _route(step_id, ANY, data["stuck"]) if data.get("stuck") else None
    if not data.get("say") and not any(r.label == ANY for r in listen):
        raise ValueError(f"step {step_id}: silent step needs an '{ANY}' route")
    if data.get("run_on") and not any(r.label == ANY for r in listen):
        raise ValueError(f"step {step_id}: run_on step needs an '{ANY}' route")
    answered_by = data.get("answered_by", "")
    if answered_by:
        if "answer" not in re.compile(answered_by).groupindex:
            raise ValueError(f"step {step_id}: answered_by needs an (?P<answer>...) group")
        if not data.get("capture") or not any(r.label == ANY for r in listen):
            raise ValueError(f"step {step_id}: answered_by needs a capture and an '{ANY}' route")
        if re.search(answered_by, ""):
            raise ValueError(f"step {step_id}: answered_by must not match an empty reply")
    if data.get("echo") and not data.get("capture"):
        raise ValueError(f"step {step_id}: echo needs a capture")
    for line in (data.get("say", ""), data.get("say_plain", ""), *probes,
                 *(r.get("ack", "") for r in [*(data.get("listen") or {}).values(), data.get("stuck") or {}])):
        _one_stress(f"step {step_id}", line)
    unsure = data.get("unsure", "")
    if unsure and not any(r.label == unsure and r.examples and r.then != step_id for r in listen):
        raise ValueError(f"step {step_id}: unsure {unsure!r} must name one of its answers that moves on")
    return Step(
        step_id, stage, data.get("say", ""), data.get("say_plain", ""),
        data.get("capture", ""), probes,
        listen, bool(data.get("run_on")),
        data.get("name", ""), data.get("note", ""), bool(data.get("doubts_answer")),
        stuck, answered_by, bool(data.get("echo")), unsure, bool(data.get("moment")),
    )


def _one_stress(where, line):
    """A line stresses one word at most: stress everywhere is stress nowhere."""
    if stresses(line) > 1:
        raise ValueError(f"{where}: at most one stress mark (_word_ or ==words==) per line: {line!r}")


def blanks(line):
    """The names of the {blanks} in a line."""
    return {m.group(1) for m in BLANK.finditer(line or "")}


def _objection(name, data):
    if not data.get("examples"):
        raise ValueError(f"objection {name}: needs examples, or it can never be heard")
    return Objection(name, tuple(data["examples"]), str(data["enter"]), data.get("early", ""))


def _with_matrix(name, data, matrix):
    """The method's steps, then the objection matrix's (so they count as past the price), with the
    matrix's exit names (resell, payment, follow_up) pointed at the method's own steps by `exits`."""
    if data.get("objections"):
        raise ValueError(f"method {name}: objections live in the objection_handling file")
    if matrix is None:
        return data, {}, ""
    exits = {str(k): str(v) for k, v in (data.get("exits") or {}).items()}
    mine = {str(k): v for k, v in data["steps"].items()}
    theirs = {str(k): v for k, v in copy.deepcopy(matrix["steps"]).items()}  # its exits are rewritten
    if set(mine) & set(theirs):
        raise ValueError(f"method {name}: steps {sorted(set(mine) & set(theirs))} are also matrix steps")
    used = {"follow_up"}  # an objection past the limit books it
    for step in theirs.values():
        for route in [*(step.get("listen") or {}).values(), *([step["stuck"]] if step.get("stuck") else [])]:
            then = str(route["then"])
            if then not in theirs:
                used.add(then)
                route["then"] = exits.get(then, then)  # an unknown name fails below as an unknown then
    if set(exits) != used:
        raise ValueError(f"method {name}: exits must name exactly {sorted(used)}")
    if any(v not in mine for v in exits.values()):
        raise ValueError(f"method {name}: exits must lead to the method's own steps")
    objections = {k: _objection(k, v) for k, v in matrix["objections"].items()}
    if any(o.enter not in theirs for o in objections.values()):
        raise ValueError(f"method {name}: every objection must enter at a matrix step")
    return {**data, "steps": {**mine, **theirs}}, objections, exits["follow_up"]


def _reachable(name, first, steps, starts):
    """Fails loud on a step no route, objection or shortcut can lead to: it would never be said."""
    seen, todo = set(), [first, *starts]
    while todo:
        step_id = todo.pop()
        if step_id not in seen:
            seen.add(step_id)
            todo += [r.then for r in steps[step_id].routes]
    if set(steps) - seen:
        raise ValueError(f"method {name}: steps {sorted(set(steps) - seen)} can never be reached")


def parse_method(name, data, matrix=None):
    """Build a Method from parsed YAML; `matrix` is its objection_handling file. Fails loud on a broken
    script graph."""
    data, objections, follow_up = _with_matrix(name, data, matrix)
    steps = {str(k): _step(str(k), v) for k, v in data["steps"].items()}
    first = str(data.get("first", ""))
    if first not in steps:
        raise ValueError(f"method {name}: first step {first!r} not defined")
    for step in steps.values():
        for route in step.routes:
            if route.then not in steps:
                raise ValueError(f"step {step.id}: unknown then {route.then!r}")
        if step.listen and not step.stuck and not any(r.label == ANY for r in step.listen):
            raise ValueError(f"step {step.id}: can be asked again, so it needs a 'stuck' route")
    echo = {s.capture for s in steps.values() if s.echo}
    for step in steps.values():  # the echo budget may say a line without their words: it needs a plain one
        if blanks(step.say) & echo and not step.say_plain:
            raise ValueError(f"step {step.id}: a line with their words in it needs a say_plain")
        if any(blanks(p) & echo for p in step.probes):
            raise ValueError(f"step {step.id}: probes never say their words back (no plain line to fall back to)")
    price_step = str(data.get("price_step", ""))
    if price_step not in steps:
        raise ValueError(f"method {name}: price_step {price_step!r} not defined")
    reask = tuple(data.get("reask") or ())
    if any("?" in r for r in reask):
        raise ValueError(f"method {name}: reask leads must not ask (the step's question follows)")
    for o in objections.values():
        if "?" in o.early:
            raise ValueError(f"objection {o.name}: early line must not ask (the step's question follows)")
    revisit_step = str(data.get("revisit_step", ""))
    if objections and not revisit_step:
        raise ValueError(f"method {name}: needs a revisit_step, or a worry parked before the price never comes back")
    if revisit_step:
        order = list(steps)
        if revisit_step not in steps or order.index(revisit_step) < order.index(price_step):
            raise ValueError(f"method {name}: revisit_step {revisit_step!r} must be a step at or after the price")
        if not steps[revisit_step].stuck:
            raise ValueError(f"method {name}: revisit_step {revisit_step!r} needs a 'stuck' route")
    ready = _ready(name, data.get("ready"), steps)
    _reachable(name, first, steps, [o.enter for o in objections.values()] + [s for s in (follow_up, ready and ready.then) if s])
    return Method(name, first, steps, objections, price_step, follow_up, revisit_step, ready, reask)


def _score(where, value):
    if not isinstance(value, (int, float)) or not 0 < value <= 1:
        raise ValueError(f"{where}: min_score must be a number above 0 and at most 1")
    return float(value)


def _ready(name, data, steps):
    if not data:
        return None
    if not data.get("examples"):
        raise ValueError(f"method {name}: ready needs examples")
    ready = Ready(tuple(data["examples"]), str(data.get("then", "")), str(data.get("until", "")),
                  _score(f"method {name} ready", data.get("min_score")))
    order = list(steps)
    if ready.then not in steps or ready.until not in steps:
        raise ValueError(f"method {name}: ready then/until must be defined steps")
    seen, todo = set(), [ready.then]  # every step the shortcut can lead to stays past `until`: no loop
    while todo:
        step_id = todo.pop()
        if step_id in seen:
            continue
        seen.add(step_id)
        if order.index(step_id) < order.index(ready.until):
            raise ValueError(f"method {name}: ready leads back to step {step_id}, before until, so it could repeat")
        todo += [r.then for r in steps[step_id].routes]
    return ready


def parse_offer(name, data):
    facts = {
        k: Fact(
            tuple(v.get("examples") or ()), v["answer"],
            v.get("late_answer", ""),
        )
        for k, v in (data.get("facts") or {}).items()
    }
    return Offer(
        name, int(data["months"]), str(data["price"]),
        tuple(data["pillars"]), facts,
        (data.get("about") or {}).get("text", ""), (data.get("about") or {}).get("after_price", ""),
    )


INTERRUPTION_KEYS = {"examples", "reply", "draft", "after", "after_wait", "min_score"}  # `draft` is accepted, never read


def parse_common_sense(data):
    for k, v in data["interruptions"].items():
        if set(v) - INTERRUPTION_KEYS:  # an old `wait: true` would silently turn a pause into a question
            raise ValueError(f"interruption {k}: unknown keys {sorted(set(v) - INTERRUPTION_KEYS)}")
    items = {
        k: Interruption(k, tuple(v["examples"]), v["reply"], v.get("after", "ask"),
                        bool(v.get("after_wait")),
                        _score(f"interruption {k}", v["min_score"]) if "min_score" in v else 0.0)
        for k, v in data["interruptions"].items()
    }
    for i in items.values():
        if i.after not in AFTER:
            raise ValueError(f"interruption {i.name}: after must be one of {AFTER}")
        _one_stress(f"interruption {i.name}", i.reply)
    nudge = data.get("nudge") or {}
    if "?" in data["park"] or "?" in nudge.get("reply", "") or any(
            "?" in i.reply for i in items.values() if i.after != "wait"):
        raise ValueError("park, nudge and interruption replies must not ask (the step's question follows)")
    if bool(nudge.get("reply")) != bool(nudge.get("phrases")):
        raise ValueError("nudge needs both a reply and phrases")
    unclear = data.get("unclear") or {}
    ask_meaning = data.get("ask_meaning", "")
    if ask_meaning and ("{said" not in ask_meaning or "?" not in ask_meaning):
        raise ValueError("ask_meaning must ask (a '?') about their words (a {said} blank)")
    return CommonSense(data["park"], data["revisit"], items,
                       nudge.get("reply", ""), tuple(nudge.get("phrases") or ()),
                       tuple(unclear.get("examples") or ()),
                       _score("unclear", unclear.get("min_score")) if unclear else 1.0, ask_meaning)


def parse_meanings(data):
    items = {}
    for k, v in (data.get("meanings") or {}).items():
        if not v.get("examples") or not v.get("lines"):
            raise ValueError(f"meaning {k}: needs examples and lines")
        for line in v["lines"]:
            if "?" in line or "{" in line:
                raise ValueError(f"meaning {k}: a line neither asks nor has blanks (the step's question follows): {line!r}")
            _one_stress(f"meaning {k}", line)
        items[k] = Meaning(k, tuple(v["examples"]), tuple(v["lines"]))
    min_words = data.get("min_words", 2)
    if not isinstance(min_words, int) or isinstance(min_words, bool) or min_words < 1:
        raise ValueError("meanings: min_words must be a whole number of at least 1")
    return Meanings(items, _score("meanings", data.get("min_score")), min_words)


def load_method(name, directory=CONFIG_DIR / "methods", shared=CONFIG_DIR / "script"):
    """`shared`: where the objection_handling file the method names lives."""
    data = _read(directory, name)
    handling = data.get("objection_handling")
    return parse_method(name, data, _read(shared, handling) if handling else None)


def load_offer(name, directory=CONFIG_DIR / "offers"):
    return parse_offer(name, _read(directory, name))


def load_common_sense(name="common_sense", directory=CONFIG_DIR / "script"):
    return parse_common_sense(_read(directory, name))


def load_meanings(name="meanings", directory=CONFIG_DIR / "script"):
    return parse_meanings(_read(directory, name))
