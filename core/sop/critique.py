"""The written critique: a short paragraph summing up an SOP's checklist, or how a call followed the SOP.

Rules decide what it says (what is missing first, how many steps went unsaid); config/sop.yaml `critique` has the
words. Same result in, same paragraph out.
"""

from __future__ import annotations

from core.sop.adherence import Adherence
from core.sop.checklist import ElementResult


def _join(items: list[str]) -> str:
    """"a", "a and b", "a, b and c"."""
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def sop_critique(elements: list[ElementResult], cfg: dict) -> str:
    """What the SOP is missing, the costliest gap first."""
    words, rank = cfg["critique"]["sop"], cfg["critique"]["priority"]
    missing = sorted((e for e in elements if not e.covered), key=lambda e: rank.index(e.id) if e.id in rank else len(rank))
    if not missing:
        return words["complete"]
    first, others = missing[0], missing[1:]
    parts = [words["gaps"].format(covered=len(elements) - len(missing), total=len(elements),
                                  first=first.label.lower(), why=first.why)]
    if others:
        parts.append(words["more"].format(others=_join([e.label.lower() for e in others])))
    parts.append(words["advice"])
    return " ".join(parts)


def call_critique(result: Adherence, cfg: dict) -> str:
    """How the call followed the SOP: the share done, the first step skipped, whether the order held."""
    words = cfg["critique"]["call"]
    counted = [s for s in result.steps if s.done or not s.conditional]
    if not counted:
        return words["none_counted"]
    done = sum(s.done for s in counted)
    parts = [words["strong" if result.score >= words["strong_from"] else "weak"].format(
        done=done, counted=len(counted), score=result.score)]
    skipped = [s for s in counted if not s.done]
    if skipped:
        parts.append(words["skipped_first"].format(step=skipped[0].step, stage=skipped[0].stage))
        if len(skipped) > 1:
            more = len(skipped) - 1
            parts.append(words["skipped_more"].format(more=more, steps="step" if more == 1 else "steps"))
    if done > 1:
        parts.append(words["order" if result.in_order else "out_of_order"])
    return " ".join(parts)
