"""Starting a practice call part way through, at a stage (config/script/stage_jump.yaml). Shared by both modes:

- buy mode: the learner is the prospect; the AI seller starts at the stage's step with the recap answers saved.
- sell mode: the learner is the rep; the AI buyer starts on a short call so far, the script's questions
  answered with the recap answers, so the learner's next line is the stage's own.

Either way the learner first sees the recap ("So far, you/they said") and may change the answers."""

import random
import re

from core.buy_mode.script_engine.method import load_method, load_stage_jump


def stage_starts(method, samples=None):
    """Where a jump to each stage lands, and the answers taken as given before it:
    [{stage, step, name, recap: [{slot, question, answer, ask}]}]. `question` is the recap's plain label, `ask`
    the script's line that asked for it. `samples` replaces the method's own sample answers (sell mode fills
    them from the buyer's persona)."""
    cfg = load_stage_jump().get(method.name, {})
    samples = cfg.get("samples", {}) if samples is None else samples
    labels, asks, order = cfg.get("labels", {}), cfg.get("asks", {}), list(method.steps)
    out = []
    for stage, step_id in cfg.get("starts", {}).items():
        step = method.steps.get(step_id)
        if not step or not step.say:
            continue
        before = [method.steps[k] for k in order[:order.index(step_id)] if k not in method.talks]
        recap = [{"slot": s.capture, "question": labels.get(s.capture) or s.name or s.capture,
                  "answer": samples[s.capture], "ask": asks.get(s.id) or s.say_plain or s.say}
                 for s in before if s.capture and s.capture in samples]
        out.append({"stage": stage, "step": step_id, "name": step.name or step_id, "recap": recap})
    return out


def kept_answers(starts, stage, answers):
    """The recap answers for `stage` as the learner left them: only the slots its recap offered, short plain
    strings, empty ones dropped. None for a stage with no start."""
    start = next((s for s in starts if s["stage"] == stage or s["step"] == stage), None)
    if start is None:
        return None
    offered = {r["slot"] for r in start["recap"]}
    answers = answers if isinstance(answers, dict) else {}
    return start, {k: str(v).strip()[:200] for k, v in answers.items()
                   if k in offered and isinstance(v, str) and v.strip()}


# ---- sell mode ------------------------------------------------------------------------------

def _sell_cfg():
    return load_stage_jump()["sell"]


def _sell_method():
    return load_method(_sell_cfg()["method"])


def _persona_fill(persona):
    """The persona's own words for the sample templates: {need}, {need2}, {pain}, {pain2}."""
    needs = [str(n) for n in persona.get("needs") or []] or ["this"]
    pains = [str(p) for p in persona.get("pain_points") or []] or ["it isn't working"]
    return {"need": needs[0], "need2": needs[min(1, len(needs) - 1)],
            "pain": pains[0], "pain2": pains[min(1, len(pains) - 1)]}


def sell_samples(persona):
    """The buyer's answers so far, in their persona's words, first letter capitalised."""
    fill = _persona_fill(persona)
    out = {}
    for slot, template in _sell_cfg()["samples"].items():
        text = re.sub(r"\{(\w+)\}", lambda m: fill.get(m.group(1), m.group(0)), template)
        out[slot] = text[:1].upper() + text[1:]
    return out


def sell_stage_starts(persona):
    return stage_starts(_sell_method(), sell_samples(persona))


def sell_history(persona, stage, answers):
    """The call so far for a sell-mode jump to `stage`: each recap question (the rep, the learner's side) and the
    buyer's answer, ending with the buyer. [] at the first stage (the buyer's normal opening is used). ValueError
    for an unknown stage."""
    starts = sell_stage_starts(persona)
    kept = kept_answers(starts, stage, answers)
    if kept is None:
        raise ValueError(f"no stage to start at: {stage!r}")
    start, answers = kept
    history = []
    for item in start["recap"]:
        answer = answers.get(item["slot"])
        if answer:
            history += [{"role": "user", "content": item["ask"]}, {"role": "assistant", "content": answer}]
    return history
