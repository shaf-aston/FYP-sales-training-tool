"""Make the voice's lines ahead of time, so they play at once (core/infra/providers/speech.py keeps every line said).

    nice -n 19 python -m scripts.speech_prewarm [--dry-run]

On the VM's 2 ARM cores a fresh sentence takes about as long to make as to say; most of what a learner hears is
fixed, though: the sell-mode buyer's bank lines and objections (in each persona's own voice) and buy mode's script
(the seller's voice). This makes each of those sentences once, split exactly as the web asks for them, oldest-first
by how often they come up. Already made: skipped, so it can run after every deploy (scripts/deploy_vm.sh starts it
in the background, at the lowest priority, so it never slows a live call).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from core.infra.loader import load_buyer_config, load_yaml
from core.infra.providers.speech import SPEECH, is_cached, kokoro, pick_voice, speak, spoken_sentences
from core.sell_mode.buyer_lines import fill

TEXT_KEYS = {"say", "say_plain", "probe", "probes", "ack", "reply", "answer", "late_answer", "late_again", "bridge",
             "reask", "lines", "text"}


def _strings(node, keys=TEXT_KEYS, inside=False):
    """Every string under one of `keys`, anywhere in a YAML tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, keys, inside or k in keys)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, keys, inside)
    elif isinstance(node, str) and inside:
        yield node


def buyer_lines() -> dict[str, set[str]]:
    """{voice: sentences} for every persona: its bank lines filled with each of its own needs and pains, the
    difficulty profiles' objections and the openers."""
    cfg = load_buyer_config()
    bank = load_yaml("prospect_lines.yaml")["lines"]
    objections = [o["text"] for p in cfg["difficulty_profiles"].values() for o in p.get("objection_bank", [])]
    out: dict[str, set[str]] = {}
    for group in cfg["personas"].values():
        for persona in group:
            voice = pick_voice("buyer", persona["name"])
            lines: list[str] = list(objections)
            for cells in bank.values():
                for templates in cells.values():
                    for t in templates:
                        if "{" not in t:
                            lines.append(t)
                            continue
                        for need in persona.get("needs", [""]):
                            for pain in persona.get("pain_points", [""]):
                                text = fill(t, {**persona, "needs": [need], "pain_points": [pain]}, "")
                                if text:
                                    lines.append(text)
            for openers in cfg.get("opening_lines", {}).values():
                for t in openers:
                    try:
                        lines.append(t.format(name=persona["name"], background=persona["background"][:1].lower()
                                              + persona["background"][1:], need=persona["needs"][0]))
                    except (KeyError, IndexError):
                        pass
            out.setdefault(voice, set()).update(s for line in lines for s in spoken_sentences(line))
    return out


def seller_lines() -> set[str]:
    """Buy mode's seller: the script's own lines (no blanks), the shared script and every offer's answers."""
    root = Path(__file__).resolve().parent.parent / "config"
    texts = []
    for path in [*root.glob("methods/*.yaml"), *root.glob("script/*.yaml"), *root.glob("offers/*.yaml")]:
        texts += [t for t in _strings(load_yaml(str(path.relative_to(root)))) if "{" not in t]
    return {s for t in texts for s in spoken_sentences(t)}


def main(dry: bool = False) -> None:
    jobs = [(SPEECH["kokoro"]["seller"], s) for s in sorted(seller_lines(), key=len)]
    for voice, sentences in buyer_lines().items():
        jobs += [(voice, s) for s in sorted(sentences, key=len)]
    todo = [(v, s) for v, s in dict.fromkeys(jobs) if not is_cached(s, v)]
    print(f"{len(jobs)} sentences, {len(todo)} to make", flush=True)
    if dry:
        return
    kokoro()
    start, made = time.time(), 0
    for voice, sentence in todo:
        if speak(sentence, voice=voice, engines=["kokoro"]):
            made += 1
        if made and made % 50 == 0:
            print(f"{made}/{len(todo)} made, {time.time() - start:.0f}s", flush=True)
    print(f"done: {made} made in {time.time() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main(dry="--dry-run" in sys.argv)
