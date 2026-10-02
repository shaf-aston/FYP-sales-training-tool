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
