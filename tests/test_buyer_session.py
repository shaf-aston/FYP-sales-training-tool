"""The AI buyer: difficulty sets how often it pushes back, and a turn, rewind or redo leaves it consistent."""

import pytest

from core.buyer_session import BuyerSession
from core.providers.base import LLMResponse


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

    turn = next(t for t in range(1, TURNS + 1) if buyer.pacer.for_turn(t))
    replies = [buyer.process_turn("What matters most to you here?").content for _ in range(turn)]

    # A session that sold or walked early stops recording prompts, which would
    # otherwise surface as a bare IndexError if difficulty tuning ever changed.
    assert len(prompts) >= turn, (
        f"the buyer ended the session at turn {len(prompts)}, before the objection "
        f"due at turn {turn} - retune the fixture, not the assertion"
    )
    objection = buyer.pacer.for_turn(turn)
    assert replies[turn - 1] == f"Go on. {objection['text']}"
    assert "THIS TURN" not in prompts[turn - 1]
    assert buyer.state.objections_raised == 1


def test_a_turn_that_never_reached_the_buyer_leaves_no_trace(stub_buyer):
    """An outage must not count the turn, move readiness, or leave a half turn
    in the transcript - otherwise resending the same line banks it twice."""
    from core.buyer_session import ProviderUnavailable

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

