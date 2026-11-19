"""Manager insights: a team's skill levels from its members' skill history, and coaching guidelines from rules.

Pure logic: callers pass each member's entries (oldest first, the web's skill log shape), the skills (sell_service
.skills()), the target, the clock and config/insights.yaml. Every guideline is a sentence from config with the
numbers that triggered it filled in, so a manager can always see why it says what it says.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

_DAY_MS = 86_400_000


@dataclass(frozen=True)
class MemberInsight:
    user_id: int
    name: str
    sessions: int
    last_at: int | None           # ms since epoch of their latest scored session
    levels: dict[str, int]        # skill id -> average of their last `window` sessions that measured it
    weakest: str | None           # the skill furthest below target (None when too early, or none below)
    judged: bool                  # enough sessions to rank


def _levels(entries: list[dict], ids: list[str], window: int) -> dict[str, int]:
    out = {}
    for sid in ids:
        seen = [e["scores"][sid] for e in entries if sid in e["scores"]][-window:]
        if seen:
            out[sid] = round(sum(seen) / len(seen))
    return out


def _weakest(levels: dict[str, int], ids: list[str], target: int) -> str | None:
    gaps = [(target - levels[sid], -i, sid) for i, sid in enumerate(ids) if sid in levels and levels[sid] < target]
    return max(gaps)[2] if gaps else None


def _change(entries: list[dict], sid: str, window: int) -> int | None:
    """Latest-`window` average minus the `window` before it, when both exist."""
    seen = [e["scores"][sid] for e in entries if sid in e["scores"]]
    if len(seen) < 2 * window:
        return None
    recent, before = seen[-window:], seen[-2 * window:-window]
    return round(sum(recent) / window - sum(before) / window)


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def build_insights(members: list[tuple[int, str, list[dict]]], skills: list[dict], target: int, now_ms: int,
                   cfg: dict) -> dict:
    """`members`: (user id, name, skill entries oldest first). Returns members, team levels and guidelines."""
    ids = [s["id"] for s in skills]
    label = {s["id"]: s["label"] for s in skills}
    tip = {s["id"]: s["tip"] for s in skills}
    window, words = cfg["window"], cfg["guidelines"]

    people = []
    for user_id, name, entries in members:
        levels = _levels(entries, ids, window)
        judged = len(entries) >= cfg["min_sessions"]
        people.append(MemberInsight(user_id, name, len(entries), entries[-1]["at"] if entries else None, levels,
                                    _weakest(levels, ids, target) if judged else None, judged))

    judged = [p for p in people if p.judged]
    team = {sid: round(sum(p.levels[sid] for p in judged if sid in p.levels) / n)
            for sid in ids if (n := sum(sid in p.levels for p in judged))}

    guidelines = []
    below = {sid: [p for p in judged if p.levels.get(sid, target) < target] for sid in ids}
    # The team's gap: the skill most members are below target on; on a tie, the one the team is lowest on.
    worst = max(ids, key=lambda sid: (len(below[sid]), -team.get(sid, target))) if ids else None
    if judged and worst and len(below[worst]) * 2 > len(judged):
        guidelines.append(words["team_gap"].format(skill=label[worst], below=len(below[worst]), judged=len(judged),
                                                   target=target, tip=tip[worst]))
    for p in sorted(judged, key=lambda p: -(target - p.levels.get(p.weakest, target)) if p.weakest else 0):
        if p.weakest and p.weakest != worst:
            guidelines.append(words["member_gap"].format(name=p.name, skill=label[p.weakest],
                                                         score=p.levels[p.weakest], target=target))
    for user_id, name, entries in members:
        best = max(((c, sid) for sid in ids if (c := _change(entries, sid, window)) is not None), default=None)
        if best and best[0] >= cfg["rising_points"]:
            guidelines.append(words["rising"].format(name=name, skill=label[best[1]], change=best[0]))
    idle = [p.name for p in people if p.last_at is None or now_ms - p.last_at > cfg["inactive_days"] * _DAY_MS]
    if idle:
        guidelines.append(words["inactive"].format(count=len(idle), members=_plural(len(idle), "member", "members"),
                                                   have=_plural(len(idle), "has", "have"), days=cfg["inactive_days"],
                                                   names=", ".join(idle)))
    early = [p.name for p in people if not p.judged]
    if early:
        guidelines.append(words["too_early"].format(count=len(early), members=_plural(len(early), "member", "members"),
                                                    have=_plural(len(early), "has", "have"), min=cfg["min_sessions"],
                                                    names=", ".join(early)))
    if judged and not any(p.weakest for p in judged):
        guidelines.append(words["all_met"])

    return {"target": target, "skills": skills, "team": team, "members": [asdict(p) for p in people],
            "guidelines": guidelines}
