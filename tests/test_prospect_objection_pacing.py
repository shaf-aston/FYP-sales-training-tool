"""The difficulty setting must actually change how often the buyer pushes back.

Before this, objection_probability, objection_bank and max_objections were read by
nothing, so "easy" and "hard" played the same and the counter in the buyer's prompt
was stuck at 0 forever.
"""

import pytest

from core.prospect_session import ProspectSession
from core.providers.base import LLMResponse


class StubProspectProvider:
    provider_name = "stub"

    def get_model_name(self):
        return "stub-model"

    def chat(self, messages, temperature=0.7, max_tokens=150):
        return LLMResponse(content="Alright, go on.")


@pytest.fixture(autouse=True)
def stub_provider(monkeypatch):
    monkeypatch.setattr(
        "core.prospect_session.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )


def session(difficulty, session_id="s1"):
    return ProspectSession(difficulty=difficulty, session_id=session_id)


TURNS = 30


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_the_buyer_never_raises_more_objections_than_the_profile_allows(difficulty):
    prospect = session(difficulty)
    cap = prospect._objection_cap()

    assert cap > 0
    assert prospect._objections_raised_by(TURNS) == cap
    assert prospect._objections_raised_by(TURNS * 10) == cap


def test_a_harder_buyer_pushes_back_sooner():
    """Averaged over many sessions, so this compares the profiles, not one roll."""
    session_ids = [f"seed-{n}" for n in range(40)]

    def mean_first_objection_turn(difficulty):
        first_turns = []
        for sid in session_ids:
            prospect = session(difficulty, sid)
            first_turns.append(
                next(
                    (t for t in range(1, TURNS + 1) if prospect._objection_for_turn(t)),
                    TURNS,
                )
            )
        return sum(first_turns) / len(first_turns)

    easy = mean_first_objection_turn("easy")
    medium = mean_first_objection_turn("medium")
    hard = mean_first_objection_turn("hard")

    assert hard < medium < easy


def test_hard_raises_strictly_more_objections_than_easy():
    assert session("hard")._objection_cap() > session("easy")._objection_cap()


def test_objections_come_out_of_the_bank_in_order_and_never_repeat():
    prospect = session("hard")
    issued = [
        prospect._objection_for_turn(turn)
        for turn in range(1, TURNS + 1)
    ]
    raised = [o for o in issued if o is not None]
    bank = prospect.difficulty_profile["objection_bank"]

    assert raised == bank[: prospect._objection_cap()]
    assert len(raised) == len({id(o) for o in raised})


def test_the_same_turn_always_rolls_the_same_way():
    """A redone turn must not silently change the buyer's later objections."""
    first = session("medium", "abc")
    second = session("medium", "abc")

    assert [first._turn_dice(t) for t in range(1, 10)] == [
        second._turn_dice(t) for t in range(1, 10)
    ]
    assert first._objections_raised_by(9) == second._objections_raised_by(9)


def test_two_sessions_do_not_get_identical_objection_timing():
    timings = {
        sid: tuple(bool(session("medium", sid)._objection_for_turn(t)) for t in range(1, 12))
        for sid in ("aaa", "bbb", "ccc")
    }

    assert len(set(timings.values())) > 1


def test_rewinding_puts_the_objection_count_back():
    prospect = session("medium", "rewind-me")
    prospect.conversation_history = [
        {"role": "assistant", "content": "Hi."},
        {"role": "user", "content": "What brought you in today?"},
        {"role": "assistant", "content": "Looking around."},
        {"role": "user", "content": "What matters most to you here?"},
        {"role": "assistant", "content": "Price, mostly."},
    ]
    prospect.state.turn_count = 2
    prospect.state.objections_raised = 99

    assert prospect.rewind_to_turn(2) is True
    assert prospect.state.objections_raised == prospect._objections_raised_by(1)


def test_a_live_turn_tells_the_buyer_to_raise_the_objection_and_counts_it():
    """The wiring: the helpers above are useless if process_turn ignores them."""
    prospect = session("hard", "wiring")
    prompts = []
    prospect.provider.chat = lambda messages, **kw: (
        prompts.append(messages[0]["content"]) or LLMResponse(content="Go on.")
    )

    turn = next(t for t in range(1, TURNS + 1) if prospect._objection_for_turn(t))
    for _ in range(turn):
        prospect.process_turn("What matters most to you here?")

    assert "THIS TURN: raise your" in prompts[turn - 1]
    assert prospect.state.objections_raised >= 1
    assert f"Objections raised so far: {prospect.state.objections_raised}" in prompts[turn - 1]


def test_the_dead_needs_list_is_gone():
    """Nothing read it, so it was removed rather than given a made-up meaning."""
    prospect = session("easy")

    assert "needs_disclosed" not in prospect.state.to_dict()
    assert "needs_disclosed" not in prospect.to_dict()["state"]
