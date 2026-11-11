"""engine.yaml fails loudly when a seller is built, naming the key, not mid-call."""
import pytest

from core.buy_mode.script_engine.config import check, problems
from core.infra.loader import load_yaml

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
    (lambda c: c["products"]["consultative_coaching"].pop("label"), "products.consultative_coaching.label: needs text"),
    (lambda c: c["products"]["consultative_coaching"].update(blurb=" "), "products.consultative_coaching.blurb: needs text"),
    (lambda c: c["filler_words"].append(True), "filler_words: every item is text"),  # a bare yes in YAML
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
    from core.buy_mode.script_engine.method import (
        load_common_sense,
        load_method,
        load_offer,
    )
    from core.buy_mode.script_engine.seller import ScriptSeller

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
    from core.buy_mode.script_engine.method import parse_common_sense
    data = load_yaml("script/common_sense.yaml")
    data = {**data, "unclear": {k: v for k, v in data["unclear"].items() if k != "min_score"}}
    with pytest.raises(ValueError, match="unclear: min_score"):
        parse_common_sense(data)


@pytest.mark.parametrize("key, value", [("wait_again", "Still there?"), ("yes_no_reask", ["Yes or no?"]),
                                        ("park_again", "Still worried?")])
def test_lines_said_before_a_question_never_ask(key, value):
    """The step's question follows them: a "?" in front would be two questions in one message."""
    from core.buy_mode.script_engine.method import parse_common_sense
    data = {"park": "", "revisit": "", "interruptions": {}, key: value}
    with pytest.raises(ValueError, match="must not ask"):
        parse_common_sense(data)
    assert parse_common_sense({**data, key: ["Sure."] if key == "yes_no_reask" else "Sure."})


def test_a_sense_can_count_only_as_a_question():
    """`only_asked`: "does that matter?" asks why, "that matters to me" answers."""
    from core.buy_mode.script_engine.method import parse_common_sense
    sense = {"examples": ["why do you ask"], "reply": "It helps.", "only_asked": True}
    data = {"park": "", "revisit": "", "interruptions": {"why_ask": sense, "thanks": {"examples": ["thanks"], "reply": "Sure."}}}
    found = parse_common_sense(data).interruptions
    assert found["why_ask"].only_asked and not found["thanks"].only_asked


def test_a_sense_can_count_only_before_the_price():
    """`before_price`: "I'm not interested" early leaves; from the price on the close hears it its own way."""
    from core.buy_mode.script_engine.method import parse_common_sense
    data = {"park": "", "revisit": "", "interruptions": {
        "not_interested": {"examples": ["no thank you"], "reply": "", "after": "follow_up", "before_price": True},
        "thanks": {"examples": ["thanks"], "reply": "Sure."}}}
    found = parse_common_sense(data).interruptions
    assert found["not_interested"].before_price and not found["thanks"].before_price
