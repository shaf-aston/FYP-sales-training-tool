"""engine.yaml checked once, when a seller is built: a missing key, a wrong type or a prompt blank the code
never fills fails loudly there, not mid-call (where an AI line's error is swallowed as "the AI failed")."""

from string import Formatter

NUMBER = (int, float)

TYPES = {
    "method": str, "products": dict, "default_product": str,
    "embed_model": str, "embed_cache_dir": str, "embed_threads": int, "embed_batch_size": int,
    "threshold": NUMBER, "early_objection_min_score": NUMBER, "early_objection_judge_score": NUMBER, "interrupt_threshold": NUMBER,
    "question_answer_min_score": NUMBER, "asked_back": dict, "asked_back_you": list, "asked_back_what": list, "what_alone_with": list, "asked_back_share": NUMBER, "sense_over_after": list, "sense_over_words": list, "asked_back_share_with_answer": NUMBER, "asked_back_min_words": int, "word_back_words": int, "word_back_skip": list, "word_back_ends": list, "clarify_starts": list, "clause_min_words": int, "clause_breaks": list, "break_not_before": list, "ask_tails": list,
    "near_miss": NUMBER, "margin": NUMBER, "close_call_k": int, "unsure_margin": NUMBER, "spell_cutoff": NUMBER, "spell_swap_min_letters": int, "spell_drop_min_letters": int, "short_replies": dict, "apostrophe_words": dict, "nudge_yes": list,
    "max_words": int, "slot_words": int, "echo_term_words": int, "echo_repeats": int, "lead_repeats": int, "takes_back": list, "objection_entries": int, "misses": int, "spell_min_letters": int,
    "ai_retries": int, "ai_rest_seconds": NUMBER, "ai_fail_limit": int, "ai_timeout_seconds": NUMBER,
    "ai_workers": int, "judge_examples": int, "judge_tokens": int, "answer_tokens": int, "listen_tokens": int,
    "ack_tokens": int, "ack_retries": int, "ack_max_words": int, "probe_max_words": int, "memory_chars": int,
    "log_text_chars": int, "rise_answer_words": int, "reason_starts": list, "reason_backs": list, "amount_per": dict, "filler_leads": list, "end_tags": list, "check_tags": list, "spell_keep_lists": list, "tags_alone_mean": list, "lead_not_before": list,
    "ack": bool, "listen": bool, "log_uncovered": bool,
    "stop_words": list, "side_words": list, "filler_words": list, "no_answer_words": list, "no_words": list, "no_polite_words": list, "filler_tags": list, "tag_skip": list, "question_words": list, "question_subjects": list, "question_starts": list, "closed_question_starts": list, "question_lead_words": list,
    "bad_phrase_starts": list, "echo_not_with": list, "verb_goal_starts": list, "verb_goal_leads": list, "be_goal_words": list, "echo_drop_starts": list, "echo_drop_ends": list, "echo_cut_at": list, "echo_want_words": list, "echo_want_within": int, "echo_cleft_starts": list, "echo_cleft_verbs": list, "echo_reason_starts": list, "money_signs_as": str, "sure_marks": list, "sure_marks_as": str, "answer_labels": list, "emoji_words": dict, "word_swaps": dict, "flip_leads": list, "echo_want_objects": list, "form_joins": dict, "echo_drop_words": list, "echo_drop_verbs": list, "echo_list_joins": list, "echo_drop_verbs_not_before": list,
    "prospect_pronouns": list, "spell_word_endings": list, "spell_words": list, "spell_real_words": str, "answer_banned_words": list,
    "vague_words": list, "shrug_phrases": list, "openers": list, "fact_presses": int, "banned_phrases": list, "nudge_leads": list, "nudge_after_break": list, "take_backs": list, "denied_leads": list, "answer_leads": list, "aside_starts": list, "unsure_leads": list, "unsure_ends": list, "ask_leads": list, "take_backs_with_break": list, "take_backs_mid": list, "ack_words": list,
    "number_blanks": dict, "number_words": dict, "number_skip": list, "number_half": str, "number_parts": dict, "echo_pronoun_swap": dict, "coach_notes": dict, "prompts": dict,
    "uncovered_fallback": str, "bridge_ack": str, "corrects": str, "corrects_drop": str,
}

# the blanks the code fills in each template; a template may leave any of them out, never add one
BLANKS = {
    "prompts": {
        "ack": {"question", "reply", "max_words", "memory"},
        "ack_memory": {"told"},
        "answer": {"facts", "question", "memory"},
        "answer_memory": {"told"},
        "judge": {"options", "vague", "reply", "answers"},
        "listen": {"concept", "question", "reply", "max_words", "probe_words", "memory"},
    },
    "coach_notes": {"step": {"title", "name"}, "listen": {"note"}, "default": None},  # None: said as is, never formatted
}


def _blanks(template):
    """The names a template fills: {told[0]} and {slot.x} need `told` and `slot`."""
    return {name.split(".")[0].split("[")[0] for _, name, _, _ in Formatter().parse(template) if name is not None}


def problems(cfg):
    """Every way `cfg` breaks what the engine reads from it, as readable lines; [] when it is fine."""
    found = []
    for key, kind in TYPES.items():
        if key not in cfg:
            found.append(f"{key}: missing")
        elif not isinstance(cfg[key], kind) or (kind is not bool and isinstance(cfg[key], bool)):
            found.append(f"{key}: expected {getattr(kind, '__name__', 'number')}, got {type(cfg[key]).__name__}")
        elif kind is list and (odd := [w for w in cfg[key] if not isinstance(w, str)]):
            found.append(f"{key}: every item is text; quote {odd} (YAML reads a bare yes/no/on/off as true/false)")
    for section, templates in BLANKS.items():
        for name, allowed in templates.items():
            template = cfg.get(section, {}).get(name) if isinstance(cfg.get(section), dict) else None
            if not isinstance(template, str):
                found.append(f"{section}.{name}: missing")
                continue
            if allowed is None:
                continue
            try:
                unknown = _blanks(template) - allowed
            except ValueError as exc:  # an unpaired { or }
                found.append(f"{section}.{name}: {exc}")
                continue
            if unknown:
                found.append(f"{section}.{name}: unknown blanks {sorted(unknown)} (allowed {sorted(allowed)})")
    if isinstance(cfg.get("products"), dict) and cfg.get("default_product") not in cfg["products"]:
        found.append(f"default_product: {cfg.get('default_product')!r} is not one of products")
    return found


def check(cfg):
    """`cfg` as is, or a ValueError naming every problem at once."""
    found = problems(cfg)
    if found:
        raise ValueError("engine.yaml:\n  " + "\n  ".join(found))
    return cfg


def plain_words(cfg):
    """Words that carry no answer on their own: "the", "um", "stuff"."""
    return frozenset(cfg["stop_words"]) | frozenset(cfg["filler_words"]) | frozenset(cfg["vague_words"])
