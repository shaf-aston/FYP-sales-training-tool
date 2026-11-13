"""How a call went, stage by stage: what the seller found out, in what order, and how deep they went.

Rules only, no AI. The stages and the human reason each one matters are in config/call_stages.yaml (they follow the
CAT script's thinking). Reads the turns session_review.build_review already annotated (seller line, buyer reply,
the buyer line before, turn_rating signals), so the stages and the turn ratings can never disagree about a turn.

Each stage comes back as {id, name, status, says, why, next, turns}: status is strong, partly, missed, early, weak
or none (nothing to judge, e.g. no objection was raised), and turns are the evidence (turn numbers).
"""

from __future__ import annotations

import re

from core.infra.loader import load_yaml
from core.infra.utils import tokenize
from core.sell_mode.buyer_moves import asks_to_commit, states_price, topic_of
from core.training.turn_rating import load_turn_rating

ORDER = ("opening", "goals", "situation", "problem", "obstacle", "playback", "solution", "price", "objections", "close")
GOOD = ("strong", "none")   # a stage with nothing to work on


def _cfg() -> dict:
    return load_yaml("call_stages.yaml")


def _has(phrases: list[str], text: str) -> bool:
    """A phrase said in the text: whole words, or a word's start ("frustrat" -> "frustrated")."""
    low = (text or "").lower().replace("’", "'")
    return any(re.search(rf"(?<![a-z']){re.escape(p)}", low) for p in phrases)


def _asked(line: str) -> bool:
    return "?" in (line or "")


def _told(line: str, phrases: list[str]) -> bool:
    """A statement sentence (no question mark) in the line says one of the phrases: an offer, a playback."""
    return any(_has(phrases, s) for s in re.split(r"(?<=[.!?])\s+", line or "") if s and not s.rstrip().endswith("?"))


def _content_words(text: str) -> set[str]:
    stop = {w.lower() for w in load_turn_rating().get("mirroring_stopwords", [])}
    return {w for w in tokenize(text or "") if len(w) > 2 and w not in stop}


def _stage(sid: str, status: str, turns: list[int]) -> dict:
    spec = _cfg()["stages"][sid]
    return {"id": sid, "name": spec["name"], "status": status, "says": spec.get(status, ""), "why": spec["why"],
            "next": "" if status in GOOD else spec.get("next", ""), "turns": sorted(set(turns))}


def analyse_stages(turns: list[dict]) -> list[dict]:
    """The call's stages, in call order. `turns`: build_review's annotated turns."""
    d = _cfg()["detect"]
    seller = [t["seller"] or "" for t in turns]
    num = [t["turn"] for t in turns]
    asked = [_asked(s) for s in seller]
    topic = [topic_of(s) if a else "general" for s, a in zip(seller, asked)]
    heard: list[set[str]] = []   # the buyer's words up to each turn (what the seller could play back)
    words: set[str] = set()
    for t in turns:
        words |= _content_words(t.get("buyer_before", ""))
        heard.append(set(words))
    out = []

    # opening: the first thing asked is about them
    first_q = next((i for i, a in enumerate(asked) if a), None)
    pitched_first = bool(seller) and _told(seller[0], d["offer"])
    if seller and asked[0] and not pitched_first:
        out.append(_stage("opening", "strong", [num[0]]))
    elif first_q is not None and first_q <= 1:
        out.append(_stage("opening", "partly", [num[first_q]]))
    else:
        out.append(_stage("opening", "missed", [num[0]] if seller else []))

    # what they want, and how far past the first answer
    goal = [i for i, (s, a, tp) in enumerate(zip(seller, asked, topic)) if a and (
        tp == "need" or _has(d["goal"], s) or (_has(d["dig"], s) and _has(d["identity"], s)))]   # "what would that mean for you personally?"
    if not goal:
        out.append(_stage("goals", "missed", []))
    else:
        digs = [i for i in range(goal[0] + 1, len(seller)) if asked[i] and (
            _has(d["dig"], seller[i]) or ("on_topic" in turns[i]["signals"] and topic[i] in ("need", "general")))]
        deep = [i for i in [goal[0], *digs] if _has(d["identity"], seller[i])]
        status = "strong" if deep or len(digs) >= 2 else "partly"
        out.append(_stage("goals", status, [num[i] for i in [goal[0], *digs[:3]]]))

    # where they are now, and what they have tried
    # an open question about today, not "shall we get you started today?"
    # ... nor "what made you take this call today?", which asks why they came, not how they do it now
    now = [i for i, s in enumerate(seller) if "open_question" in turns[i]["signals"] and not _has(d["about_them"], s)
           and (topic[i] == "current" or _has(d["situation"], s))]
    tried = [i for i, s in enumerate(seller) if asked[i] and _has(d["tried"], s)]
    status = "strong" if now and tried else "partly" if now or tried else "missed"
    out.append(_stage("situation", status, [num[i] for i in now[:2] + tried[:2]]))

    # the problem, how long, what it costs
    kinds = {"pain": [], "duration": [], "consequence": []}
    for i, tp in enumerate(topic):
        if asked[i] and tp in kinds:
            kinds[tp].append(i)
    found = [k for k, v in kinds.items() if v]
    problem_at = min((v[0] for v in kinds.values() if v), default=None)
    status = ("strong" if kinds["consequence"] and len(found) >= 2 else "partly" if found else "missed")
    out.append(_stage("problem", status, [num[v[0]] for v in kinds.values() if v]))

    # what has kept them stuck
    stuck = [i for i, s in enumerate(seller) if asked[i] and _has(d["obstacle"], s)]
    out.append(_stage("obstacle", "strong" if stuck else "missed", [num[i] for i in stuck[:2]]))

    # the offer: where it came, and whether it is in their words
    offers = [i for i, s in enumerate(seller) if _told(s, d["offer"])]
    first_offer = offers[0] if offers else len(seller)
    playback = [i for i in range(first_offer + (0 if offers else 0)) if i < len(seller) and (
        _told(seller[i], d["playback"]) or (not asked[i] and len(_content_words(seller[i]) & heard[i]) >= d["playback_min_words"]))]
    playback += [first_offer] if offers and _has(d["playback"], seller[first_offer]) else []
    out.append(_stage("playback", "strong" if playback else "missed", [num[i] for i in playback[:2]]))
    goal_or_problem = min([x for x in (goal[0] if goal else None, problem_at) if x is not None], default=None)
    if not offers:
        out.append(_stage("solution", "missed", []))
    elif first_offer < d["early_turns"] or goal_or_problem is None or first_offer < goal_or_problem:
        out.append(_stage("solution", "early", [num[first_offer]]))
    else:
        tied = [i for i in offers if len(_content_words(seller[i]) & heard[i]) >= d["offer_min_words"]]
        out.append(_stage("solution", "strong" if tied else "partly", [num[i] for i in (tied or offers)[:2]]))

    # the price: after the cost of the problem, or before it
    price = next((i for i, s in enumerate(seller) if states_price(s)), None)
    if price is None:
        out.append(_stage("price", "missed", []))
    else:
        valued = problem_at is not None and problem_at < price
        out.append(_stage("price", "strong" if valued else "early", [num[price]]))

    # doubt: what the seller did with the turn after the buyer pushed back
    handled = []
    for i, t in enumerate(turns[:-1]):
        if _has(d["doubt"], t.get("buyer") or ""):
            nxt = turns[i + 1]
            sig = nxt["signals"]
            if "pressure" in sig or _has(d["argue"], nxt["seller"]):
                handled.append(("weak", nxt["turn"]))
            elif ("acknowledgement" in sig or _has(d["acknowledge"], nxt["seller"])) and _asked(nxt["seller"]):
                handled.append(("strong", nxt["turn"]))
            else:
                handled.append(("partly", nxt["turn"]))
    if not handled:
        out.append(_stage("objections", "none", []))
    else:
        kinds_seen = {k for k, _ in handled}
        status = "weak" if "weak" in kinds_seen else "strong" if kinds_seen == {"strong"} else "partly"
        out.append(_stage("objections", status, [n for _, n in handled]))

    # the next step
    ask = [i for i, s in enumerate(seller) if asks_to_commit(s)]
    if not ask:
        out.append(_stage("close", "missed", []))
    else:
        early = goal_or_problem is None or ask[0] < goal_or_problem
        out.append(_stage("close", "early" if early else "strong", [num[i] for i in ask[:2]]))
    return out


def focus(stages: list[dict]) -> dict | None:
    """The one stage to work on next: the earliest in the call that was not strong (the later ones build on it)."""
    return next((s for s in stages if s["status"] not in GOOD), None)
