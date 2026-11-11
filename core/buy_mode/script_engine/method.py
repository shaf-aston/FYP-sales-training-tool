"""Load and validate sales-method and offer YAML into frozen dataclasses."""

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from core.buy_mode.script_engine.words.fill import NAME, blanks
from core.buy_mode.script_engine.words.tone import stresses
from core.buy_mode.stage import Stage
from core.infra.loader import CONFIG_DIR
from core.infra.utils import normal

ANY = "any"  # listen route with no examples: taken for any reply
# What happens after an interruption's reply: ask the step again (same words), wait for them to come
# back, ask it in other words, (a step with no other words) move on to the next step, or book the follow-up.
AFTER = ("ask", "wait", "rephrase", "rephrase_else_move_on", "follow_up")


def says(pattern, text):
    """A rule's regex (`pattern`, case-blind) finds its words in the reply; an empty pattern never does."""
    return bool(pattern) and re.search(pattern, text, re.IGNORECASE) is not None


def _checked_pattern(where, pattern):
    """A rule's regex, failing loud at load: it must compile and must not match an empty reply (it would take every one)."""
    try:
        if re.search(pattern, "", re.IGNORECASE):
            raise ValueError(f"{where} pattern must not match an empty reply")
    except re.error as e:
        raise ValueError(f"{where} pattern: {e}") from None
    return pattern


@dataclass(frozen=True)
class Route:
    label: str          # what the reply means; matched against `examples` (ANY: every reply)
    examples: tuple
    then: str
    ack: str = ""
    keep: bool = True   # false = the reply is not kept as the step's answer (a vague one restates the question)
    min_score: float = 0.0  # a match must score at least this to take the route; under it, the reply is heard as unmatched
    like: str = ""      # the shared answer (answers.yaml) it takes examples from: what kind of answer it is ("no")
    say: str = ""       # said in place of the next step's own line, which this answer would make untrue ("not long" ->
                        # not "so many nights, months and years"); on a route back to its own step, the line asked again
    pattern: str = ""   # regex: a reply it matches takes this route by rule, before any meaning ("6 weeks" is recent:
                        # the embedder puts "6 weeks" next to "6 months")
    restates: bool = False  # the answer only says the question back ("I want to make money online"): a reply that
                            # opens with it and goes on is heard by the rest ("..., so I can quit my job")
    climbs_to: tuple = ()   # routes a reply that goes on past this answer moves up to, when the rest is clearly one
                            # ("I want more money so I can stop worrying about bills": already the next rung)

    def says(self, text):
        return says(self.pattern, text)


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
    bridge: str = ""    # a getting-to-know-you question that follows a short intro of who we are (a fact with `bridge`); their reply is not saved
    reask: tuple = ()   # this step's own `reask` leads, in place of the method's ("more money" again is an answer, not a blank)
    needs: str = ""     # regex an answer must match ("how much a month?" needs a figure); a reply without it is asked again
    plain_if: str = ""  # regex: their words said back that match it get the plain line ("each month to make more money?" asks money for money)
    shrug_moves_on: bool = False  # the next line answers the question itself: a shrug ("yeah") moves on unsaved, never asked again
    yes_no: bool = False  # the question wants a yes or no but opens with no helper verb ("Open to being called out?")
    go_on_is_yes: bool = False  # the question asks to go ahead ("jumping in?"): "go on" says yes; at "keep settling?" it never does
    either: str = ""    # one of its answers' examples: a reply that leaves a choice to us ("whichever", "up to you") is heard as it

    @property
    def routes(self):
        return self.listen + ((self.stuck,) if self.stuck else ())


@dataclass(frozen=True)
class Objection:
    name: str
    examples: tuple
    enter: str           # after the price: the matrix step its branch starts at
    early: str = ""      # before the price: a short honest answer instead of `park`; may be raised while asking
    early_examples: tuple = ()   # the examples heard before the price: `after_price` ones ("money is tight") are
    # their life then, not our price (whole calls: "money has been tight" at step 01 got "I haven't mentioned a price yet")
    never_with: tuple = ()   # words that make a reply never this one ("can I do it today?" is no "another day")

    def heard(self, opened):
        """The examples that count: all once the price is out, else only the ones about paying us."""
        return self.examples if opened else self.early_examples


@dataclass(frozen=True)
class Ready:
    """A shortcut heard on every step in its window: a keen prospect says they're in before the pitch (`ready`),
    or asks how to pay once the price is out (`pays`): skip to `then` instead of making them sit through it."""
    examples: tuple
    then: str           # the step the call jumps to
    until: str          # only before this step; from here on the script itself is closing
    min_score: float    # a match must score at least this on every step ("I'm in sales" must not jump)
    start: str = ""     # only from this step on; "" = from the first
    pattern: str = ""   # words that take it whatever the examples score ("take my money"); "" = none

    def says(self, text):
        return says(self.pattern, text)


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
    pays: Ready = None      # "how do I pay?" from the price on: straight to paying
    max_visits: int = 0     # a step landed on this many times a call is going round in circles: the follow-up instead (0 = no limit)
    talks: tuple = ()  # the objection matrix's steps: while on one, a worry raised is being talked through

    @property
    def shortcuts(self):
        """{name: Ready} for the shortcuts this method has; the name is how the reply was heard ("ready:pays")."""
        return {k: r for k, r in (("prospect", self.ready), ("pays", self.pays)) if r}


@dataclass(frozen=True)
class Fact:
    examples: tuple
    answer: str
    late_answer: str    # used once the price step is reached; empty = same answer
    bridge: bool = False  # the step's `bridge` question follows the answer, in place of the step's own question
    again: str = ""     # before the price, asked a second time: a short reminder, not the same long answer twice
    pressed: str = ""   # before the price, asked `fact_presses` times: said once, the late lines after it; empty = `again`
    late_again: str = ""  # once `late_answer` (or `pressed`) was said, asked again: a short reminder; empty = `late_answer`


@dataclass(frozen=True)
class Offer:
    name: str
    months: int
    price: str
    pillars: tuple
    facts: dict
    industry: str = ""  # where the business is built ("online"): fills {industry}, so an intro stays vague about the how
    about: str = ""     # what the AI may say when no fact covers a question; empty = never answer from it
    about_after_price: str = ""  # added to `about` from the price step on
    setter: str = ""    # who booked the call: fills {setter} in the opening; empty = the plain line


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
    with_answer: bool = False  # may sit beside an answer ("3 years, what about you?"): answer kept, this said first
    only_asked: bool = False  # counts only as a question: "does that matter?" asks, "that matters to me" answers
    once: bool = False  # answered once a call: said again ("ok, thank you" after "You're welcome.") it is heard as the rest
    before_price: bool = False  # heard only before the price is out; from it on, the close hears a no its own way
    never_with: tuple = ()  # words that make a reply never this one ("I want that again" is no "say that again")
    only_with: tuple = ()  # words a reply must say to be this one: "what held me back?" asks no "what held you back?"
    until_price: tuple = ()  # more examples, heard only before the price: "is that a lot?" asks about their own figure,
    # from the price on it is the money worry

    def heard(self, opened):
        """The examples that count: `until_price` ones only before the price is out."""
        return self.examples if opened else self.examples + self.until_price


@dataclass(frozen=True)
class CommonSense:
    park: str
    revisit: str        # lead-in when a parked objection is raised again
    interruptions: dict
    nudge: str = ""     # said when a reply only nudges ("what's next?"), before carrying on
    nudges: tuple = ()  # phrases that nudge, cut off the end of a reply
    unclear: tuple = ()  # replies that give nothing to an open question ("dunno man", "stuff I guess")
    unclear_min_score: float = 1.0  # a reply counts as unclear when it matches `unclear` at least this well
    ask_meaning: tuple = ()  # ways to ask what they meant by their own words ({said}), used in turn; empty = never asked
    told_again: str = ""  # a fact asked a second time with no `again` of its own; empty = the answer again
    ended: str = ""     # said to any reply once the call has ended (a step with nowhere to go); empty = its line again
    same_words: str = ""  # in place of a rephrase's lead when the step has no other words left; empty = the lead
    wait_again: str = ""  # in place of a wait reply said just before ("brb" twice); empty = the reply again
    yes_no_reask: tuple = ()  # leads for a yes-or-no question asked again, in turn, in place of the `reask` ones
    park_again: str = ""  # a worry already parked before the price, asked about again; empty = its first line again
    corrected: str = ""  # they fixed their last answer a turn later; empty = the question again only
    unfinished: str = ""  # said to a reply cut off mid-sentence ("probably the fact that"): the next one is joined on
    unfinished_ends: tuple = ()  # last words that leave a sentence open
    no_words: str = "Sorry, I didn't catch that. Could you say it in English?"  # a reply with no readable words, or a fault while hearing it


def _read(directory, name):
    path = Path(directory) / f"{name}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=_StrictLoader)


def _route(step_id, label, data, answers):
    """`answers`: the shared answer lists (answers.yaml); `like: <name>` takes one, before the route's own examples."""
    if not isinstance(label, str):
        raise TypeError(f"step {step_id}: route name {label!r} is not text (quote yes/no)")
    like = data.get("like")
    if like is not None and like not in answers:
        raise ValueError(f"step {step_id}: route '{label}' is like unknown answer {like!r}")
    examples = tuple(dict.fromkeys([*answers.get(like, ()), *(data.get("examples") or ())]))
    if label == ANY and examples:
        raise ValueError(f"step {step_id}: '{ANY}' route takes no examples")
    if label != ANY and not examples:
        raise ValueError(f"step {step_id}: route '{label}' needs examples")
    if label == ANY and "min_score" in data:
        raise ValueError(f"step {step_id}: '{ANY}' route takes no min_score")
    floor = _score(f"step {step_id} route {label}", data["min_score"]) if "min_score" in data else 0.0
    say = data.get("say", "")
    if say and ("?" not in say or NAME.search(say)):
        raise ValueError(f"step {step_id}: route '{label}' say must ask and have no blanks")
    keep, restates = data.get("keep", True) is not False, data.get("restates", False) is True
    if restates and keep:
        raise ValueError(f"step {step_id}: route '{label}' restates the question, so it can't keep the reply")
    climbs_to = tuple(data.get("climbs_to") or ())
    pattern = data.get("pattern", "")
    if pattern:
        if label == ANY:
            raise ValueError(f"step {step_id}: '{ANY}' route takes no pattern")
        _checked_pattern(f"step {step_id}: route '{label}'", pattern)
    return Route(label, examples, str(data["then"]), data.get("ack", ""), keep, floor, like or "", say,
                 pattern=pattern, restates=restates, climbs_to=climbs_to)


def _step(step_id, data, answers):
    stage = data.get("ui_stage")
    if stage not in {s.value for s in Stage}:
        raise ValueError(f"step {step_id}: unknown ui_stage {stage!r}")
    listen = tuple(_route(step_id, k, v, answers) for k, v in (data.get("listen") or {}).items())
    probes = data.get("probe") or ()
    probes = (probes,) if isinstance(probes, str) else tuple(probes)
    stuck = _route(step_id, ANY, data["stuck"], answers) if data.get("stuck") else None
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
    needs = data.get("needs", "")
    reask = tuple(data.get("reask") or ())
    if any("?" in r for r in reask):
        raise ValueError(f"step {step_id}: reask leads must not ask (the step's question follows)")
    if needs and (not data.get("capture") or re.search(needs, "")):
        raise ValueError(f"step {step_id}: needs takes a capture and must not match an empty reply")
    plain_if = data.get("plain_if", "")
    if plain_if and not data.get("say_plain"):
        raise ValueError(f"step {step_id}: plain_if needs a say_plain")
    if data.get("shrug_moves_on") and not any(r.label == ANY for r in listen):
        raise ValueError(f"step {step_id}: shrug_moves_on needs an '{ANY}' route to move on by")
    for key in ("yes_no", "go_on_is_yes"):
        if data.get(key) and "?" not in data.get("say", ""):
            raise ValueError(f"step {step_id}: {key} needs a say that asks")
    if data.get("echo") and not data.get("capture"):
        raise ValueError(f"step {step_id}: echo needs a capture")
    for line in (data.get("say", ""), data.get("say_plain", ""), *probes, *reask,
                 *(r.get(k, "") for r in [*(data.get("listen") or {}).values(), data.get("stuck") or {}] for k in ("ack", "say"))):
        _one_stress(f"step {step_id}", line)
        if line.count("{") != len(NAME.findall(line)):
            raise ValueError(f"step {step_id}: a blank is {{name}} or {{name|noun form|verb form}}: {line!r}")
    either = data.get("either", "")
    if either and not any(either in r.examples for r in listen):
        raise ValueError(f"step {step_id}: either {either!r} must be one of its answers' examples")
    unsure = data.get("unsure", "")
    if unsure and not any(r.label == unsure and r.examples and r.then != step_id for r in listen):
        raise ValueError(f"step {step_id}: unsure {unsure!r} must name one of its answers that moves on")
    return Step(
        step_id, stage, data.get("say", ""), data.get("say_plain", ""),
        data.get("capture", ""), probes,
        listen, bool(data.get("run_on")),
        data.get("name", ""), data.get("note", ""), bool(data.get("doubts_answer")),
        stuck, answered_by, bool(data.get("echo")), unsure, bool(data.get("moment")), data.get("bridge", ""),
        reask, needs, plain_if, bool(data.get("shrug_moves_on")), bool(data.get("yes_no")),
        bool(data.get("go_on_is_yes")), either,
    )


def _one_stress(where, line):
    """A line stresses one word at most: stress everywhere is stress nowhere."""
    if stresses(line) > 1:
        raise ValueError(f"{where}: at most one stress mark (_word_ or ==words==) per line: {line!r}")


def _objection(name, data):
    if not data.get("examples"):
        raise ValueError(f"objection {name}: needs examples, or it can never be heard")
    early = tuple(data["examples"])
    return Objection(name, early + tuple(data.get("after_price", ())), str(data["enter"]), data.get("early", ""), early,
                     tuple(normal(w) for w in data.get("never_with") or ()))


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


def parse_method(name, data, matrix=None, answers=None):
    """Build a Method from parsed YAML; `matrix` is its objection_handling file, `answers` the shared answer
    lists (answers.yaml). Fails loud on a broken script graph."""
    data, objections, follow_up = _with_matrix(name, data, matrix)
    answers = {str(k): tuple(v) for k, v in (answers or {}).items()}
    steps = {str(k): _step(str(k), v, answers) for k, v in data["steps"].items()}
    first = str(data.get("first", ""))
    if first not in steps:
        raise ValueError(f"method {name}: first step {first!r} not defined")
    for step in steps.values():
        for route in step.routes:
            if route.then not in steps:
                raise ValueError(f"step {step.id}: unknown then {route.then!r}")
            if set(route.climbs_to) - {r.label for r in step.listen}:
                raise ValueError(f"step {step.id}: route '{route.label}' climbs to an unknown route")
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
    ready = _ready(name, data.get("ready"), steps, answers)
    pays = _ready(name, data.get("pays"), steps, answers)
    _reachable(name, first, steps, [o.enter for o in objections.values()]
               + [s for s in (follow_up, ready and ready.then, pays and pays.then) if s])
    max_visits = data.get("max_visits", 0)
    if not isinstance(max_visits, int) or max_visits < 0 or (max_visits and not follow_up):
        raise ValueError(f"method {name}: max_visits must be a whole number >= 0, and needs a follow_up step")
    talks = tuple(str(k) for k in (matrix or {}).get("steps", {}))
    return Method(name, first, steps, objections, price_step, follow_up, revisit_step, ready, reask, pays, max_visits, talks)


def _score(where, value):
    if not isinstance(value, (int, float)) or not 0 < value <= 1:
        raise ValueError(f"{where}: min_score must be a number above 0 and at most 1")
    return float(value)


def _ready(name, data, steps, answers):
    """A shortcut (`ready`, `pays`); its examples may be `like` a shared answer (answers.yaml)."""
    if not data:
        return None
    like = data.get("like")
    if like is not None and like not in answers:
        raise ValueError(f"method {name}: shortcut is like unknown answer {like!r}")
    examples = tuple(dict.fromkeys([*answers.get(like, ()), *(data.get("examples") or ())]))
    if not examples:
        raise ValueError(f"method {name}: ready needs examples")
    ready = Ready(examples, str(data.get("then", "")), str(data.get("until", "")),
                  _score(f"method {name} ready", data.get("min_score")), str(data.get("from", "")),
                  str(data.get("pattern", "")))
    if ready.pattern:
        _checked_pattern(f"method {name}: shortcut", ready.pattern)
    order = list(steps)
    if ready.then not in steps or ready.until not in steps or (ready.start and ready.start not in steps):
        raise ValueError(f"method {name}: ready then/until/from must be defined steps")
    if ready.start and order.index(ready.start) >= order.index(ready.until):
        raise ValueError(f"method {name}: a shortcut's from must come before its until")
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
            v.get("late_answer", ""), bool(v.get("bridge")), v.get("again", ""),
            v.get("pressed", ""), v.get("late_again", ""),
        )
        for k, v in (data.get("facts") or {}).items()
    }
    return Offer(
        name, int(data["months"]), str(data["price"]),
        tuple(data["pillars"]), facts, str(data.get("industry", "")),
        (data.get("about") or {}).get("text", ""), (data.get("about") or {}).get("after_price", ""),
        str(data.get("setter", "")),
    )


INTERRUPTION_KEYS = {"examples", "reply", "draft", "after", "after_wait", "min_score", "with_answer", "only_asked", "once", "before_price", "never_with", "only_with", "until_price"}  # `draft` is accepted, never read


def parse_common_sense(data):
    for k, v in data["interruptions"].items():
        if set(v) - INTERRUPTION_KEYS:  # an old `wait: true` would silently turn a pause into a question
            raise ValueError(f"interruption {k}: unknown keys {sorted(set(v) - INTERRUPTION_KEYS)}")
    items = {
        k: Interruption(k, tuple(v["examples"]), v["reply"], v.get("after", "ask"),
                        bool(v.get("after_wait")),
                        _score(f"interruption {k}", v["min_score"]) if "min_score" in v else 0.0,
                        v.get("with_answer", False) is True, v.get("only_asked", False) is True,
                        v.get("once", False) is True, v.get("before_price", False) is True,
                        tuple(normal(w) for w in v.get("never_with") or ()),
                        tuple(normal(w) for w in v.get("only_with") or ()),
                        tuple(v.get("until_price") or ()))
        for k, v in data["interruptions"].items()
    }
    for i in items.values():
        if i.after not in AFTER:
            raise ValueError(f"interruption {i.name}: after must be one of {AFTER}")
        if i.with_answer and i.after != "ask":
            raise ValueError(f"interruption {i.name}: with_answer only goes with after: ask (the next question follows)")
        _one_stress(f"interruption {i.name}", i.reply)
    nudge = data.get("nudge") or {}
    if "?" in data["park"] or "?" in data.get("told_again", "") or "?" in data.get("ended", "") or "?" in data.get("same_words", "") or "?" in data.get("wait_again", "") or "?" in data.get("park_again", "") or "?" in data.get("corrected", "") or any("?" in r for r in data.get("yes_no_reask") or ()) or "?" in nudge.get("reply", "") or any(
            "?" in i.reply for i in items.values() if i.after != "wait"):
        raise ValueError("park, nudge and interruption replies must not ask (the step's question follows)")
    if bool(nudge.get("reply")) != bool(nudge.get("phrases")):
        raise ValueError("nudge needs both a reply and phrases")
    unclear = data.get("unclear") or {}
    ask_meaning = data.get("ask_meaning") or ()
    ask_meaning = (ask_meaning,) if isinstance(ask_meaning, str) else tuple(ask_meaning)
    if any("{said" not in a or "?" not in a for a in ask_meaning):
        raise ValueError("ask_meaning must ask (a '?') about their words (a {said} blank)")
    return CommonSense(data["park"], data["revisit"], items,
                       nudge.get("reply", ""), tuple(nudge.get("phrases") or ()),
                       tuple(unclear.get("examples") or ()),
                       _score("unclear", unclear.get("min_score")) if unclear else 1.0, ask_meaning,
                       data.get("told_again", ""), data.get("ended", ""), data.get("same_words", ""),
                       data.get("wait_again", ""), tuple(data.get("yes_no_reask") or ()), data.get("park_again", ""),
                       data.get("corrected", ""), (data.get("unfinished") or {}).get("reply", ""),
                       tuple((data.get("unfinished") or {}).get("ends") or ()))


def load_method(name, directory=CONFIG_DIR / "methods", shared=CONFIG_DIR / "script"):
    """`shared`: where the objection_handling file the method names, and the shared answers, live."""
    data = _read(directory, name)
    handling = data.get("objection_handling")
    answers = _read(shared, "answers") if (Path(shared) / "answers.yaml").exists() else None
    return parse_method(name, data, _read(shared, handling) if handling else None, answers)


def load_offer(name, directory=CONFIG_DIR / "offers"):
    return parse_offer(name, _read(directory, name))


def load_common_sense(name="common_sense", directory=CONFIG_DIR / "script"):
    return parse_common_sense(_read(directory, name))
