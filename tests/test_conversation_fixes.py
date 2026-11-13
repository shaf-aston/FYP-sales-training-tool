"""Live conversation test, 13 Nov: the replies that did not fit what the seller said, each pinned here."""

from core.infra.loader import load_buyer_config, load_yaml
from core.sell_mode.buyer_lines import pick_line
from core.sell_mode.buyer_moves import Move, asks_to_commit, next_move, states_price, topic_of
from core.sell_mode.buyer_rules import ObjectionPacer
from core.training.turn_rating import rate_turn

OPEN = "If we could sort that, what would it change for you personally?"
TOLD = "We take the reporting off your plate and you get a weekly summary."


def _always(waits=None):
    """A pacer that rolls an objection every turn, with no waits."""
    bank = [{"type": "skepticism", "text": "How do I know it actually works?"}]
    return ObjectionPacer("s", {"objection_probability": 1.0, "max_objections": 1}, bank, waits=waits)


def test_an_open_question_gets_an_answer_not_an_objection():
    """"What would it change for you?" got "Stakeholder confidence. That sounds good on paper, but how do I know it
    actually works?": the objection waits for a turn where the seller told them something."""
    pacer = _always()
    said = [OPEN, OPEN, TOLD]
    assert pacer.for_turn(1, said) is None and pacer.for_turn(2, said) is None
    assert pacer.for_turn(3, said)["type"] == "skepticism"


def test_a_yes_no_question_can_still_draw_an_objection():
    assert _always().for_turn(1, ["Would a weekly summary make a difference?"]) is not None


def test_a_chosen_objection_still_comes_on_turn_one_whatever_was_asked():
    pacer = ObjectionPacer("s", {"objection_probability": 0.0, "max_objections": 0}, [], first={"type": "chosen", "text": "Too dear."})
    assert pacer.for_turn(1, ["What made you take this call today?"])["text"] == "Too dear."


def test_without_the_seller_lines_the_pacer_behaves_as_before():
    assert _always().for_turn(1) is not None   # rewinds and old callers pass no lines


def test_the_price_told_gets_a_reaction_to_the_price():
    """"It's four thousand for the year." got "I like the sound of that.\""""
    for line in ["It's four thousand for the year.", "The investment is $4,000 for the year.", "It's 4k all in."]:
        assert states_price(line), line
        assert next_move(0.5, line, []).topic == "price"
    assert not states_price("How much would you want to spend?")
    assert not states_price("We help owners cut the admin that eats the week.")
    bank = load_yaml("prospect_lines.yaml")["lines"]
    assert all("price" in bank[kind] for kind in ("lean_in", "ask", "stall"))


def test_what_happens_if_nothing_changes_asks_about_the_stakes():
    """"What happens if nothing changes?" got "Risk mitigation, mostly." (a need line)."""
    for line in ["And what happens if nothing changes over the next year?", "What is that admin costing you each month?"]:
        assert topic_of(line) == "consequence", line
    assert next_move(0.8, "What happens if nothing changes?", ["open_question"]).label == "share:consequence"


def test_sign_you_up_asks_them_to_commit():
    """"So shall I sign you up now?" got "A few things. I'd rather hear what you do first.\""""
    assert asks_to_commit("So shall I sign you up now?")
    assert "closed_question" in rate_turn("So shall I sign you up now?", "", 3).signals


def test_a_line_followed_by_an_objection_asks_nothing():
    """"That would help. What's the next step? I'd need to discuss this with my partner first.\""""
    move = Move("lean_in", "general", objection=True)
    for seed in range(30):
        line = pick_line(move, "", {"needs": ["x"], "pain_points": ["y"]}, [], None, str(seed))
        assert line and "?" not in line


def test_the_buyer_is_told_no_sales_jargon():
    """"Honestly, I'd compare it to the cost of inaction.\""""
    assert "cost of inaction" in load_buyer_config()["system_prompt_template"]


def test_small_talk_and_payment_questions_have_answers():
    """"I'm good thanks" got "You're welcome."; "What would the payments look like?" got "I'll find out"."""
    sense = load_yaml("script/common_sense.yaml")
    assert "I'm good thanks" in str(sense) and "Glad to hear it." in str(sense)
    assert "what would the payments look like" in str(load_yaml("offers/shay_coaching.yaml"))


def test_a_real_question_that_starts_like_a_greeting_is_not_a_stock_one():
    """"How are you handling the admin at the moment?" was rated a stock question, like "How are you?"."""
    assert "open_question" in rate_turn("How are you handling the admin at the moment?", "", 3).signals
    assert "open_question" in rate_turn("What do you do when that happens?", "", 3).signals
    for stock in ["How are you?", "Hi, how are you doing today?", "What do you do?", "Anything else?"]:
        assert "generic_question" in rate_turn(stock, "", 3).signals, stock
