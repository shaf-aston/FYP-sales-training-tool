"""Reframe #1 of the Objection Handling Matrix (Sales Sniper SOP), step by step.

The SOP's dialogue expects an answer at each question ("Yes, of course." / "Well, no." / "No, I don't."), and its
flow chart sends a "No" at a reframe on to the next reframe. A reply that is no answer at all is asked again,
never taken as the expected one (live, 13 Nov: "you" to the mindset question was heard as "Yes, of course.")."""
import pytest

from test_script_scenarios import CAT, seller

YES_NO_REASK = "No pressure either way."


@pytest.mark.parametrize("step", ["m_reframe1", "m_reframe1_now", "m_reframe1_dictate"])
@pytest.mark.parametrize("said", ["you", "lol", "hmm"])
def test_no_answer_is_asked_again_never_taken_as_the_expected_one(fake_embedder, step, said):
    s = seller(fake_embedder, step=step)
    reply, _ = s.reply(said)
    assert s.state.step == step
    assert reply.startswith(YES_NO_REASK)


@pytest.mark.parametrize("step, said, then", [
    # Q1 "Do you feel your mindset affects your decision-making process?" (SOP: "Yes, of course.")
    ("m_reframe1", "yes of course", "m_reframe1_now"),
    ("m_reframe1", "no", "m_reframe2"),                 # this reframe has no grip: the flow chart's "No"
    ("m_reframe1", "not sure", "m_reframe1_now"),
    # Q2 "Are you 100% with where you are at right now?" (SOP: "Well, no.")
    ("m_reframe1_now", "no", "m_reframe1_dictate"),
    ("m_reframe1_now", "not really", "m_reframe1_dictate"),
    ("m_reframe1_now", "yes", "m_reframe2"),            # content where they are: no gap to work with
    # Q3 "Do you want that decision making process to dictate your results?" (SOP: "No, I don't.")
    ("m_reframe1_dictate", "no I don't", "m_reframe1_why"),
    ("m_reframe1_dictate", "yes", "m_reframe2"),
])
def test_each_answer_takes_the_sops_path(fake_embedder, step, said, then):
    s = seller(fake_embedder, step=step)
    s.reply(said)
    assert s.state.step == then


@pytest.mark.parametrize("step, then", [
    ("m_reframe1", "m_reframe1_now"), ("m_reframe1_now", "m_reframe1_dictate"), ("m_reframe1_dictate", "m_reframe2"),
])
def test_asked_again_and_still_no_answer_the_call_moves_on(fake_embedder, step, then):
    s = seller(fake_embedder, step=step)
    for _ in range(4):
        s.reply("you")
        if s.state.step != step:
            break
    assert s.state.step == then


def test_the_sops_own_dialogue_runs_straight_through(fake_embedder):
    """Reframe #1 as the SOP writes it: yes, no, no, then "Why not?"."""
    s = seller(fake_embedder, step="m_reframe1")
    for said in ["Yes, of course.", "Well, no.", "No, I don't."]:
        s.reply(said)
    assert s.state.step == "m_reframe1_why"
    assert CAT.steps["m_reframe1_why"].say == "Why not?"
