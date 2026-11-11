"""Does the SOP cover what a good sales call needs (config/sop.yaml `elements`)? Rules first: a step covers every
element whose cues it says ("If they're not ready, book a follow-up" is the close's fallback and the follow-up). A step
no cue catches falls back to meaning: the one element whose examples it is most like, if close enough. The first step
that covers an element is kept as evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.infra.utils import says_unnegated
from core.sop.match import Embed, similarity
from core.sop.outline import Stage


@dataclass(frozen=True)
class ElementResult:
    id: str
    label: str
    covered: bool
    step: str | None        # the SOP step that covers it
    why: str                # why it matters (shown when it is missing)


def _by_cues(step: str, cues: dict[str, list[re.Pattern]]) -> list[str]:
    """The elements whose cues the step says, not negated ("Don't ask about budget" says no budget step)."""
    return [eid for eid, patterns in cues.items() if says_unnegated(step, patterns)]


def check_elements(stages: list[Stage], cfg: dict, embed: Embed) -> list[ElementResult]:
    elements = cfg["elements"]
    cues = {e["id"]: [re.compile(c, re.IGNORECASE) for c in e.get("cues", [])] for e in elements}
    steps = [step for stage in stages for step in stage.steps]
    covering: dict[str, str] = {}
    unmatched = []
    negated = [re.compile(c, re.IGNORECASE) for c in cfg["negated_step"]]
    for step in steps:
        if any(p.search(step) for p in negated):   # "Never ...", "Do not ...": a rule against something
            continue
        hits = _by_cues(step, cues)
        for eid in hits:
            covering.setdefault(eid, step)
        if not hits:
            unmatched.append(step)
    if unmatched:
        examples = [(e["id"], example) for e in elements for example in e["examples"]]
        for step, row in zip(unmatched, similarity(unmatched, [x for _, x in examples], embed)):
            top = max(range(len(row)), key=row.__getitem__)
            if row[top] >= cfg["thresholds"]["element_fallback"]:
                covering.setdefault(examples[top][0], step)
    return [ElementResult(e["id"], e["label"], e["id"] in covering, covering.get(e["id"]), e["why"]) for e in elements]
