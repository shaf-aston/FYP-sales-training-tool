"""The AI buyer: difficulty sets how often it pushes back, and a turn, rewind or redo leaves it consistent."""

import pytest

from core.sell_mode.buyer_session import BuyerSession
from core.infra.providers.base import LLMResponse


@pytest.fixture(autouse=True)
def _stub(stub_buyer):
    stub_buyer.reply = "Alright, go on."


def session(difficulty, session_id="s1"):
    return BuyerSession(difficulty=difficulty, session_id=session_id)


TURNS = 30


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_the_buyer_never_raises_more_objections_than_the_profile_allows(difficulty):
    buyer = session(difficulty)
    cap = buyer.pacer.cap

    assert cap > 0
    assert buyer.pacer.raised_by(TURNS) == cap
    assert buyer.pacer.raised_by(TURNS * 10) == cap


def test_a_harder_buyer_pushes_back_sooner():
    """Averaged over many sessions, so this compares the profiles, not one roll."""
    session_ids = [f"seed-{n}" for n in range(40)]

    def mean_first_objection_turn(difficulty):
        first_turns = []
        for sid in session_ids:
            buyer = session(difficulty, sid)
            first_turns.append(
                next(
                    (t for t in range(1, TURNS + 1) if buyer.pacer.for_turn(t)),
                    TURNS,
                )
            )
        return sum(first_turns) / len(first_turns)

    easy = mean_first_objection_turn("easy")
    medium = mean_first_objection_turn("medium")
    hard = mean_first_objection_turn("hard")

    assert hard < medium < easy


def test_hard_raises_strictly_more_objections_than_easy():
    assert session("hard").pacer.cap > session("easy").pacer.cap


def test_objections_come_out_of_the_bank_in_order_and_never_repeat():
    buyer = session("hard")
    issued = [
        buyer.pacer.for_turn(turn)
        for turn in range(1, TURNS + 1)
    ]
    raised = [o for o in issued if o is not None]
    bank = buyer.pacer.bank

    assert raised == bank[: buyer.pacer.cap]
    assert len(raised) == len({id(o) for o in raised})


def test_the_same_turn_always_rolls_the_same_way():
    """A redone turn must not silently change the buyer's later objections."""
    first = session("medium", "abc")
    second = session("medium", "abc")

    assert [first.pacer.dice(t) for t in range(1, 10)] == [
        second.pacer.dice(t) for t in range(1, 10)
    ]
    assert first.pacer.raised_by(9) == second.pacer.raised_by(9)


def test_two_sessions_do_not_get_identical_objection_timing():
    timings = {
        sid: tuple(bool(session("medium", sid).pacer.for_turn(t)) for t in range(1, 12))
        for sid in ("aaa", "bbb", "ccc")
    }

    assert len(set(timings.values())) > 1


def test_rewinding_puts_the_objection_count_back():
    buyer = session("medium", "rewind-me")
    buyer.conversation_history = [
        {"role": "assistant", "content": "Hi."},
        {"role": "user", "content": "What brought you in today?"},
        {"role": "assistant", "content": "Looking around."},
        {"role": "user", "content": "What matters most to you here?"},
        {"role": "assistant", "content": "Price, mostly."},
    ]
    buyer.state.turn_count = 2
    buyer.state.objections_raised = 99

    assert buyer.rewind_to_turn(2) is True
    assert buyer.state.objections_raised == buyer.pacer.raised_by(1)


def test_a_live_turn_answers_first_then_adds_the_scripted_objection_and_counts_it(stub_buyer):
    """The wiring: the helpers above are useless if process_turn ignores them."""
    buyer = session("hard", "wiring")
    prompts = []
    stub_buyer.chat = lambda messages, **kw: (
        prompts.append(messages[0]["content"]) or LLMResponse(content="Go on.")
    )

    line = "What matters most to you here?"
    turn = next(t for t in range(1, TURNS + 1) if buyer.pacer.for_turn(t, [line] * t))
    replies = [buyer.process_turn(line).content for _ in range(turn)]

    # A session that sold or walked early stops recording prompts, which would
    # otherwise surface as a bare IndexError if difficulty tuning ever changed.
    assert len(prompts) >= turn, (
        f"the buyer ended the session at turn {len(prompts)}, before the objection "
        f"due at turn {turn} - retune the fixture, not the assertion"
    )
    objection = buyer.pacer.for_turn(turn, buyer.seller_lines())
    assert replies[turn - 1] == f"Go on. {objection['text']}"
    assert "THIS TURN" in prompts[turn - 1] and objection["text"] not in prompts[turn - 1]   # rules add it, not the AI
    assert buyer.state.objections_raised == 1


def test_a_turn_that_never_reached_the_buyer_leaves_no_trace(stub_buyer):
    """An outage must not count the turn, move readiness, or leave a half turn
    in the transcript - otherwise resending the same line banks it twice."""
    from core.sell_mode.buyer_session import ProviderUnavailable

    buyer = session("medium", "outage")
    buyer.conversation_history = [{"role": "assistant", "content": "Hi there."}]
    before = (
        buyer.state.turn_count,
        buyer.state.readiness,
        buyer.state.objections_raised,
        list(buyer.conversation_history),
    )

    def dead(messages, **kw):
        raise ProviderUnavailable("every provider is down")

    stub_buyer.chat = dead

    with pytest.raises(ProviderUnavailable):
        buyer.process_turn("Walk me through what a bad week looks like.")

    assert (
        buyer.state.turn_count,
        buyer.state.readiness,
        buyer.state.objections_raised,
        buyer.conversation_history,
    ) == before


def test_a_session_always_gets_an_id_of_its_own():
    """A blank id saves nothing, logs nothing, and shares its dice with every
    other blank-id session."""
    first = BuyerSession(difficulty="hard", session_id="")
    second = BuyerSession(difficulty="hard", session_id="")

    assert first.session_id and second.session_id
    assert first.session_id != second.session_id


def test_a_rewind_restores_the_exact_readiness_not_the_rounded_one():
    buyer = session("medium", "precision")
    buyer.conversation_history = [
        {"role": "assistant", "content": "Hi."},
        {"role": "user", "content": "What made that start to matter to you?"},
        {"role": "assistant", "content": "It costs me time."},
        {"role": "user", "content": "Buy now, today only."},
        {"role": "assistant", "content": "Hm."},
    ]
    buyer.state.turn_count = 2

    assert buyer.rewind_to_turn(2) is True
    assert buyer.state.readiness == buyer.review()["readiness_exact"]



# --- an objection waits until the call has got to it (buyer.yaml objection_waits) ---

QUESTIONS = ["What made you take this call?", "What's been the hardest part?", "How long has that been going on?"]
PITCH = "We help small businesses cut the admin that eats their week."


def _first_raised(buyer, said):
    return next(((t, o) for t in range(1, len(said) + 1) if (o := buyer.pacer.for_turn(t, said))), (None, None))


def test_a_pitch_makes_the_does_it_work_objection_ready():
    buyer = session("hard", "pitched-2")
    doubt = next(o for o in buyer.pacer.bank if o["type"] == "skepticism")
    assert not buyer.pacer.ready(doubt, 2, QUESTIONS[:2])
    assert buyer.pacer.ready(doubt, 2, [QUESTIONS[0], PITCH])


def test_no_price_or_does_it_work_objection_before_the_offer_comes_up():
    for n in range(40):
        buyer = session("hard", f"wait-{n}")
        said = QUESTIONS * 2   # six turns of questions only
        for t in range(1, 6):
            objection = buyer.pacer.for_turn(t, said)
            assert objection is None or objection["type"] not in ("price", "skepticism", "fear"), (t, objection)


def test_talk_of_money_makes_the_price_objection_ready():
    buyer = session("hard", "pitched")
    price = next(o for o in buyer.pacer.bank if o["type"] == "price")
    assert not buyer.pacer.ready(price, 2, QUESTIONS[:2])
    assert not buyer.pacer.ready(price, 2, [QUESTIONS[0], PITCH])   # a pitch alone names no price
    assert buyer.pacer.ready(price, 2, [QUESTIONS[0], "What sort of budget do you have?"])


def test_partner_and_timing_wait_a_few_turns():
    buyer = session("medium", "later")
    partner = next(o for o in buyer.pacer.bank if o["type"] == "partner")
    assert not buyer.pacer.ready(partner, 3, QUESTIONS)
    assert buyer.pacer.ready(partner, 5, QUESTIONS * 2)
    assert buyer.pacer.ready(partner, 2, [QUESTIONS[0], "Who else is involved in the decision?"])


def test_a_chosen_objection_still_comes_on_turn_one():
    buyer = BuyerSession(difficulty="medium", session_id="chosen", objection="It's too expensive.")
    assert buyer.pacer.for_turn(1, ["Hi, what made you take this call?"])["text"] == "It's too expensive."


def test_the_live_session_holds_the_premium_objection_back(stub_buyer):
    """The live call that showed it: medium, questions only, no 'what justifies the premium?' on turn 1."""
    for n in range(20):
        buyer = session("medium", f"live-{n}")
        for line in QUESTIONS:
            reply = buyer.process_turn(line).content
            assert "premium" not in reply and "actually works" not in reply, (n, line, reply)


def test_good_questions_alone_never_end_the_call_but_asking_for_the_sale_does(stub_buyer):
    """Seen in a replay: an easy buyer said 'I'm ready to move forward' after three questions, and the call was over."""
    buyer = session("easy", "asked")
    for line in ["What made you take this call?", "What's been the hardest part of that lately?",
                 "How long has that been going on?", "What are you using at the moment?",
                 "If you could fix one thing first, what would it be?"]:
        buyer.process_turn(line)
        assert not buyer.state.ended, (line, buyer.state.readiness)
    assert buyer.state.readiness >= 0.85
    buyer.process_turn("Would it make sense to get you started this week?")
    assert buyer.state.has_committed
