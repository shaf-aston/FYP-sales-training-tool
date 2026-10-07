"""Guards for the prompt text the LLM actually reads."""
import core.knowledge as knowledge
from core.prompts import STRATEGY_PROMPTS


def _all_stage_prompts():
    for strategy_block in STRATEGY_PROMPTS.values():
        for stage, text in strategy_block.items():
            yield stage, text


def test_prompts_do_not_cite_a_config_file_that_does_not_exist():
    offenders = [stage for stage, text in _all_stage_prompts() if "tactics.yaml" in text]

    assert offenders == []


def test_knowledge_block_uses_real_newlines_and_one_entry_per_field(monkeypatch):
    monkeypatch.setattr(
        knowledge,
        "load_custom_knowledge",
        lambda: {"product_name": "Acme", "selling_points": ["fast", "cheap"]},
    )

    text = knowledge.get_custom_knowledge_text()

    assert "\\n" not in text  # literal backslash-n, not a line break
    assert text == "Product name: Acme\nSelling points:\n  - fast\n  - cheap"


def test_knowledge_block_is_empty_when_nothing_is_stored(monkeypatch):
    monkeypatch.setattr(knowledge, "load_custom_knowledge", lambda: {})

    assert knowledge.get_custom_knowledge_text() == ""


def test_direct_info_override_waits_for_pitch_and_keeps_the_stage_prompt():
    from core.content import generate_stage_prompt

    ask = "what are the options and price?"
    early = generate_stage_prompt("consultative", "logical", "Acme", [], ask)
    at_pitch = generate_stage_prompt("consultative", "pitch", "Acme", [], ask)

    assert "IMMEDIATE ACTION REQUIRED" not in early
    assert "IMMEDIATE ACTION REQUIRED" in at_pitch
    assert "STAGE: PITCH" in at_pitch
    assert "|---" not in at_pitch


def test_direct_info_override_does_not_fire_at_objection():
    from core.content import generate_stage_prompt

    ask = "what are the options and price?"
    prompt = generate_stage_prompt("consultative", "objection", "Acme", [], ask)

    assert "IMMEDIATE ACTION REQUIRED" not in prompt
    assert "OBJECTION HANDLING" in prompt


def test_consultative_pre_pitch_prompt_has_no_prices_immediately_instruction():
    from core.content import generate_stage_prompt

    for stage in ("intent", "logical", "emotional"):
        prompt = generate_stage_prompt("consultative", stage, "Acme", [], "what are the options?")
        assert "IMMEDIATELY" not in prompt
        assert "Never mention products or prices before the PITCH stage" in prompt


def test_early_budget_talk_is_held_back_by_the_rules_not_a_keyword_list():
    from core.content import generate_stage_prompt

    prompt = generate_stage_prompt("consultative", "intent", "Acme", [], "my budget is 500")
    assert "Never mention products or prices before the PITCH stage" in prompt
    assert "Never name a product" in prompt


def test_each_rule_is_stated_once_per_prompt():
    from core.content import generate_stage_prompt

    for strategy, stages in STRATEGY_PROMPTS.items():
        for stage in stages:
            prompt = generate_stage_prompt(strategy, stage.replace("_low", ""), "Acme", [], "ok")
            assert prompt.count("You are a sales advisor") == 1
            assert "payment details" not in prompt  # HARD RULES already bans card, payment and bank details


def test_decisive_user_only_pushes_to_pitch_at_pitch():
    from core.loader import get_adaptation_template

    for stage in ("intent", "objection", "negotiation", "outcome"):
        text = get_adaptation_template("decisive_user", strategy="transactional", stage=stage)
        assert "to the pitch" not in text
    assert "to the pitch" in get_adaptation_template("decisive_user", strategy="transactional", stage="pitch")
