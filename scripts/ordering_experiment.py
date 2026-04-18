#!/usr/bin/env python3
"""Ordering experiment scaffold

Builds prompt variants (original, swapped tactic/history, duplicate tactic) and
sends them to a provider for side-by-side comparison. Writes JSONL results and
simple aggregated metrics.

Important: This script is a scaffold for controlled experiments. By default it
uses a synthetic `pre_state` that triggers adaptation/tactic guidance so the
effect of ordering is visible. Run with `--dry-run` first to verify prompts
locally (no external API calls).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from difflib import SequenceMatcher
from types import SimpleNamespace
from statistics import mean, median

from chatbot.chatbot import SalesChatbot
from chatbot.providers.factory import create_provider
from chatbot import content


ACK_MARKERS = ["i understand", "i see", "i hear you", "that must", "that sounds", "got it", "understand"]
PITCH_KEYWORDS = ["price", "buy", "purchase", "$", "cost"]


def build_components(strategy, stage, product_context, history, user_message, pre_state=None, objection_data=None):
    """Return prompt components same as `generate_stage_prompt` builds."""
    base = content.get_base_prompt(product_context, strategy)
    state = pre_state if pre_state is not None else content.analyse_state(history, user_message, signal_keywords=content.SIGNALS)
    preferences = content.extract_preferences(history)

    # Respect overrides — experiments should note the override behaviour
    override = content.check_override_condition(base, user_message, stage, history, preferences)
    if override:
        return {"override": True, "full": override}

    ack_guidance = content.get_ack_guidance(
        content.detect_ack_context(user_message, history, state)
    )

    tactic_guidance = content._build_tactic_guidance(strategy, state, user_message)

    stage_prompt, stage_context = content._get_stage_specific_prompt(strategy, stage, state, user_message, history, objection_data)

    preference_keyword_context = content._get_preference_and_keyword_context(history, preferences)

    turn_count = len(history) // 2
    state_block = f"""
=== TURN CONTEXT ===
Stage: {stage.upper()} | Strategy: {strategy.upper()} | Turn: {turn_count}
Intent: {state.intent} | Guarded: {'yes' if state.guarded else 'no'}
=== END CONTEXT ===
"""

    history_block = f"\nRECENT CONVERSATION:\n{content.format_conversation_context(history)}\n"

    msg_len = len(user_message.split()) if user_message else 0
    terse_guidance = ""
    if msg_len < content.TERSE_INPUT_THRESHOLD and stage != "intent":
        terse_guidance = "\nTERSE INPUT: Very short answer. Make ONE observation, then ONE question. Do not over-probe.\n"

    persona_checkpoint = ""
    if turn_count > 0 and turn_count % content.PERSONA_CHECKPOINT_TURNS == 0:
        persona_checkpoint = f"\n[CHECKPOINT — Turn {turn_count}]: Stay in {strategy} mode. One question per turn. Current stage: {stage}.\n"

    return {
        "override": False,
        "base": base,
        "state_block": state_block,
        "ack_guidance": ack_guidance,
        "stage_prompt": stage_prompt,
        "stage_context": stage_context,
        "history_block": history_block,
        "tactic_guidance": tactic_guidance,
        "preference_keyword_context": preference_keyword_context,
        "terse_guidance": terse_guidance,
        "persona_checkpoint": persona_checkpoint,
    }


def assemble_original(c):
    return (
        c["base"]
        + c["state_block"]
        + c["ack_guidance"]
        + c["stage_prompt"]
        + c["stage_context"]
        + c["history_block"]
        + c["tactic_guidance"]
        + c["preference_keyword_context"]
        + c["terse_guidance"]
        + c["persona_checkpoint"]
    )


def assemble_swapped(c):
    """Place tactic guidance before recent conversation."""
    return (
        c["base"]
        + c["state_block"]
        + c["ack_guidance"]
        + c["stage_prompt"]
        + c["stage_context"]
        + c["tactic_guidance"]
        + c["history_block"]
        + c["preference_keyword_context"]
        + c["terse_guidance"]
        + c["persona_checkpoint"]
    )


def assemble_duplicate(c):
    """Duplicate tactic guidance (before and after history)."""
    return (
        c["base"]
        + c["state_block"]
        + c["ack_guidance"]
        + c["stage_prompt"]
        + c["stage_context"]
        + c["tactic_guidance"]
        + c["history_block"]
        + c["tactic_guidance"]
        + c["preference_keyword_context"]
        + c["terse_guidance"]
        + c["persona_checkpoint"]
    )


def compute_metrics(base_text: str, resp_text: str):
    txt = resp_text or ""
    words = len(txt.split())
    q_count = txt.count("?")
    low_txt = txt.lower()
    ack = any(k in low_txt for k in ACK_MARKERS)
    pitch_leak = any(k in low_txt for k in PITCH_KEYWORDS)
    sim = SequenceMatcher(None, base_text or "", txt).ratio() if base_text else 0.0
    return {"words": words, "q_count": q_count, "ack": ack, "pitch_leak": pitch_leak, "similarity": sim}


def run(args):
    # instantiate a bot to reuse product context
    bot = SalesChatbot(provider_type=args.provider if args.provider else "dummy", model=None, product_type=args.product, session_id="ordering_experiment")
    product_context = bot.flow_engine.product_context

    # minimal history to appear in the RECENT CONVERSATION block
    history = bot.flow_engine.conversation_history or [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]

    # default pre_state to force low-intent adaptation (so tactic_guidance is present)
    pre_state = SimpleNamespace(decisive=False, intent=("low" if args.force_low_intent else "high"), guarded=False, question_fatigue=False)

    components = build_components(args.strategy, args.stage, product_context, history, args.user_message, pre_state=pre_state)
    if components.get("override"):
        print("Override prompt detected — experiment will write the override and exit.")
        out = components.get("full")
        print(out)
        return

    variants = {}
    variants["original"] = assemble_original(components)
    variants["swapped"] = assemble_swapped(components)
    variants["duplicate"] = assemble_duplicate(components)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    os.makedirs("results", exist_ok=True)
    out_path = os.path.join("results", f"ordering_experiment_{timestamp}.jsonl")

    provider = None
    if not args.dry_run:
        provider = create_provider(args.provider)

    # Run "original" first so its responses are available as the similarity baseline
    # for "swapped" / "duplicate" (the doc claim: similarity is response-vs-original-response).
    records = []
    original_responses: list[str] = []
    ordered_variants = ["original"] + [v for v in variants if v != "original"]

    for variant_name in ordered_variants:
        prompt = variants[variant_name]
        for i in range(args.runs):
            messages = [{"role": "system", "content": prompt}] + history + [{"role": "user", "content": args.user_message}]

            if args.dry_run:
                resp_text = ""  # dry-run: no provider call
            else:
                llm_resp = provider.chat(messages, temperature=args.temperature, max_tokens=args.max_tokens, stage=args.stage)
                resp_text = llm_resp.content if llm_resp and getattr(llm_resp, "content", None) else ""

            # Compare against the same-index original response when available; otherwise the first one.
            baseline_resp = ""
            if original_responses:
                baseline_resp = original_responses[i] if i < len(original_responses) else original_responses[0]
            metrics = compute_metrics(baseline_resp, resp_text)
            record = {
                "variant": variant_name,
                "run": i,
                "prompt_excerpt": prompt[:800],
                "response": resp_text,
                "metrics": metrics,
            }
            records.append(record)
            if variant_name == "original":
                original_responses.append(resp_text)

    # Write results
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Simple aggregates printed to console
    summary = {}
    for var in variants.keys():
        group = [r for r in records if r["variant"] == var]
        if not group:
            continue
        words = [g["metrics"]["words"] for g in group]
        qcounts = [g["metrics"]["q_count"] for g in group]
        acks = [g["metrics"]["ack"] for g in group]
        pitches = [g["metrics"]["pitch_leak"] for g in group]
        sims = [g["metrics"]["similarity"] for g in group]
        summary[var] = {
            "runs": len(group),
            "words_mean": mean(words) if words else 0,
            "words_median": median(words) if words else 0,
            "q_mean": mean(qcounts) if qcounts else 0,
            "ack_rate": sum(1 for x in acks if x) / len(acks) if acks else 0,
            "pitch_leak_rate": sum(1 for x in pitches if x) / len(pitches) if pitches else 0,
            "similarity_to_original_mean": mean(sims) if sims else 0,
        }

    print(f"Wrote results to: {out_path}")
    print("\nSummary:")
    print(json.dumps(summary, indent=2))

    # Sanity check: if every response is byte-identical, ordering produced no signal.
    # This is expected for `dummy` (canned reply) and `probe` (echoes prompt deterministically),
    # but means a live-provider run is required to draw any conclusion about ordering effects.
    unique_responses = {r["response"] for r in records}
    if len(unique_responses) <= 1:
        print(
            "\nWARNING: all variant responses were identical "
            f"(provider={args.provider}, dry_run={args.dry_run}). "
            "Ordering effects cannot be measured under this configuration — "
            "re-run against a real LLM provider (e.g. groq, sambanova) to get meaningful signal."
        )


def main():
    p = argparse.ArgumentParser(description="Ordering experiment for prompt assembly")
    p.add_argument("--provider", default="dummy", help="Provider key (dummy/groq/sambanova)")
    p.add_argument("--product", default=None, help="Product type for product_context (config key) or None")
    p.add_argument("--strategy", default="consultative", help="Strategy key")
    p.add_argument("--stage", default="intent", help="Stage name")
    p.add_argument("--user-message", dest="user_message", default="I need help with pricing", help="User message to test")
    p.add_argument("--runs", type=int, default=3, help="Runs per variant")
    p.add_argument("--dry-run", action="store_true", help="Build prompts and write files but do not call external providers")
    p.add_argument("--force-low-intent", dest="force_low_intent", action="store_true", help="Force low-intent pre_state to ensure tactic guidance appears")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", dest="max_tokens", type=int, default=250)
    args = p.parse_args()

    # default: set force_low_intent True so tactic guidance is present
    if not hasattr(args, "force_low_intent"):
        args.force_low_intent = True

    run(args)


if __name__ == "__main__":
    main()
