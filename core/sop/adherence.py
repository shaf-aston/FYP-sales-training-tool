"""Which SOP steps a call carried out: a step is done when one of the rep's lines means the same. Each done step keeps
the rep's line and turn number as evidence, and the call is in order when the done steps happen in SOP order."""

from __future__ import annotations

from dataclasses import dataclass

from core.sop.match import Embed, similarity
from core.sop.outline import Stage


@dataclass(frozen=True)
class StepResult:
    stage: str
    step: str
    done: bool
    turn: int | None        # the rep's turn (1-based) that carried it out
    said: str | None        # what the rep said there


@dataclass(frozen=True)
class Adherence:
    steps: list[StepResult]
    score: int              # share of steps done, 0-100
    in_order: bool          # the done steps happened in the SOP's order

    def to_json(self) -> dict:
        from dataclasses import asdict

        return {"steps": [asdict(s) for s in self.steps], "score": self.score, "in_order": self.in_order}


def check_call(stages: list[Stage], rep_lines: list[str], cfg: dict, embed: Embed) -> Adherence:
    """`rep_lines` are the rep's turns in call order."""
    flat = [(stage.title, step) for stage in stages for step in stage.steps]
    # Asymmetric: a written instruction ("Ask who signs off") searched for in what was said ("Who else decides?").
    scores = similarity([cfg["query_prefix"] + step for _, step in flat], rep_lines, embed)
    bar = cfg["thresholds"]["adherence"]
    results = []
    for (stage, step), row in zip(flat, scores):
        top = max(range(len(row)), key=row.__getitem__) if row else None
        done = top is not None and row[top] >= bar
        results.append(StepResult(stage, step, done, top + 1 if done else None, rep_lines[top] if done else None))
    turns = [r.turn for r in results if r.done]
    score = round(100 * len(turns) / len(results)) if results else 0
    return Adherence(results, score, turns == sorted(turns))
