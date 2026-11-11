"""Which SOP steps a call carried out. Each step is searched for in every sentence the rep said (a turn often does
two things), with bge's query instruction: a written instruction ("Ask who signs off") against what was said
("Who else decides?"). A step is done when its best sentence reaches the threshold; the turn and the sentence are
kept as evidence. Each sentence carries at most one step (the strongest pairs are matched first). A conditional step ("If they say it's too expensive, reframe...") is matched on its action, and
counts against the score only when it was done: its trigger may never have come up.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from core.infra.utils import sentences
from core.sop.match import Embed, similarity
from core.sop.outline import Stage


@dataclass(frozen=True)
class StepResult:
    stage: str
    step: str
    done: bool
    conditional: bool       # "If they ...": not counted against the score when not done
    turn: int | None        # the rep's turn (1-based) that carried it out
    said: str | None        # the sentence the rep said there


@dataclass(frozen=True)
class Adherence:
    steps: list[StepResult]
    score: int              # share of the steps that count (done, or not conditional) that were done, 0-100
    in_order: bool          # the done steps happened in the SOP's order

    def to_json(self) -> dict:
        return {"steps": [asdict(s) for s in self.steps], "score": self.score, "in_order": self.in_order}


def _action(step: str, condition: re.Pattern) -> tuple[str, bool]:
    """("acknowledge it and reframe around ROI", True) for "If they say it's too expensive, acknowledge it and..."."""
    m = condition.match(step)
    return (step[m.end():].strip() or step, True) if m else (step, False)


def check_call(stages: list[Stage], rep_lines: list[str], cfg: dict, embed: Embed) -> Adherence:
    """`rep_lines` are the rep's turns in call order."""
    condition = re.compile(cfg["condition"], re.IGNORECASE)
    flat = [(stage.title, step, *_action(step, condition)) for stage in stages for step in stage.steps]
    said = [(turn, s) for turn, line in enumerate(rep_lines, 1) for s in (sentences(line) or [line])]
    scores = similarity([cfg["query_prefix"] + action for _, _, action, _ in flat], [s for _, s in said], embed)
    # One sentence carries one step: strongest matches first, each step and each sentence used at most once, so
    # "what made you book the call?" cannot also count as booking a follow-up.
    bar = cfg["thresholds"]["adherence"]
    pairs = sorted(((v, i, j) for i, row in enumerate(scores) for j, v in enumerate(row) if v >= bar), reverse=True)
    match: dict[int, int] = {}
    used: set[int] = set()
    for _, i, j in pairs:
        if i not in match and j not in used:
            match[i] = j
            used.add(j)
    results = []
    for i, (stage, step, _, conditional) in enumerate(flat):
        turn, sentence = said[match[i]] if i in match else (None, None)
        results.append(StepResult(stage, step, i in match, conditional, turn, sentence))
    counted = [r for r in results if r.done or not r.conditional]
    turns = [r.turn for r in results if r.done]
    score = round(100 * sum(r.done for r in counted) / len(counted)) if counted else 0
    return Adherence(results, score, turns == sorted(turns))
