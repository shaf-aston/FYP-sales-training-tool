"""engine.yaml fails loudly when a seller is built, naming the key, not mid-call."""
import pytest

from core.loader import load_yaml
from core.script_engine.config import check, problems

CFG = load_yaml("script/engine.yaml")


def test_the_shipped_config_is_fine():
    assert problems(CFG) == []


@pytest.mark.parametrize("change, named", [
    (lambda c: c.pop("misses"), "misses: missing"),
    (lambda c: c.update(misses="3"), "misses: expected int"),
    (lambda c: c.update(misses=True), "misses: expected int"),            # a bool is not a count
    (lambda c: c.update(threshold=1), None),                               # an int is a fine number
    (lambda c: c["prompts"].update(ack="Say {reply_text}"), "prompts.ack: unknown blanks ['reply_text']"),
    (lambda c: c["prompts"].update(judge="pick {"), "prompts.judge:"),
    (lambda c: c["prompts"].pop("listen"), "prompts.listen: missing"),
    (lambda c: c["coach_notes"].update(step="{title} {why}"), "coach_notes.step: unknown blanks ['why']"),
    (lambda c: c.update(default_product="nope"), "default_product: 'nope' is not one of products"),
])
def test_a_broken_config_is_named(change, named):
    cfg = load_yaml("script/engine.yaml")
    change(cfg)
    found = problems(cfg)
    assert (found == []) if named is None else any(p.startswith(named) for p in found), found


def test_check_lists_every_problem_at_once():
    cfg = load_yaml("script/engine.yaml")
    cfg.pop("misses"), cfg.pop("ack")
    with pytest.raises(ValueError, match=r"misses: missing[\s\S]*ack: missing"):
        check(cfg)


def test_a_seller_will_not_build_on_a_broken_config(fake_embedder):
    from core.script_engine.method import load_common_sense, load_method, load_offer
    from core.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    cfg["prompts"]["ack"] = "Say {reply_text}"
    with pytest.raises(ValueError, match="reply_text"):
        ScriptSeller(cfg, load_method("cat"), load_offer("shay_coaching"), load_common_sense(), fake_embedder, None)


def test_the_unformatted_coach_default_may_hold_a_brace():
    """coach_notes.default is said as is, so a { in it is just a character."""
    cfg = {**CFG, "coach_notes": {**CFG["coach_notes"], "default": "Answer honestly {or not}."}}
    assert problems(cfg) == []


def test_an_indexed_blank_counts_as_its_name():
    """{note[0]} and {note.x} fill from `note`, an allowed blank."""
    cfg = {**CFG, "coach_notes": {**CFG["coach_notes"], "listen": "Listen for: {note[0]}"}}
    assert problems(cfg) == []


def test_an_unclear_sense_without_min_score_is_named_not_a_key_error():
    from core.script_engine.method import parse_common_sense
    data = load_yaml("script/common_sense.yaml")
    data = {**data, "unclear": {k: v for k, v in data["unclear"].items() if k != "min_score"}}
    with pytest.raises(ValueError, match="unclear: min_score"):
        parse_common_sense(data)
