"""Blocks -> the SOP's stages and steps. Each heading starts a stage; the lines under it are its steps (a long
paragraph is split into its sentences, each a step). Text before any heading forms an opening stage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.infra.constants import SOP_LIMITS
from core.sop.document import Block


@dataclass
class Stage:
    title: str
    steps: list[str] = field(default_factory=list)


def _steps(text: str) -> list[str]:
    if len(text) <= SOP_LIMITS["max_step_chars"]:
        return [text]
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_outline(blocks: list[Block], untitled: str) -> list[Stage]:
    """Stages in document order, without empty ones. The top heading level present marks stages (the next one down
    when the top holds a single title); deeper headings are steps. `untitled` names text before the first stage."""
    levels = sorted({b.level for b in blocks if b.level})
    top = levels[0] if levels else 0
    # One heading at the top level is the document's title: the level under it holds the stages.
    if len(levels) > 1 and sum(b.level == top for b in blocks) == 1:
        top = levels[1]
    stages: list[Stage] = []
    for block in blocks:
        if block.level and block.level < top:   # the title: not a stage, not a step
            continue
        if top and block.level == top:
            stages.append(Stage(block.text))
            continue
        if not stages:
            stages.append(Stage(untitled))
        stages[-1].steps.extend(s[: SOP_LIMITS["max_step_chars"]] for s in _steps(block.text))
    kept = [s for s in stages if s.steps][: SOP_LIMITS["max_stages"]]
    for stage in kept:
        stage.steps = stage.steps[: SOP_LIMITS["max_steps_per_stage"]]
    return kept
