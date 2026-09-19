"""The seller-turn judge reads what the salesperson did, not buyer keywords."""

import pytest

from core.prospect_session import ProspectSession
from core.selling_quality import load_selling_signals, score_seller_turn


def test_closed_question_does_not_beat_a_real_discovery_question():
    """The old keyword scorer gave "Are you interested?" a perfect 5 because
    "interested" is a BUYER buying-signal. It must not outscore real discovery."""
    lazy = score_seller_turn("Are you interested?")
    discovery = score_seller_turn(
        "What is your budget and timeline, and who else is involved in this decision?"
    )

    assert lazy.rating < discovery.rating


def test_harmless_sentence_is_not_read_as_the_seller_walking_out():
    """"not for me" is a buyer walking away; from a seller it is ordinary speech."""
    score = score_seller_turn("Honestly that is not for me to say, but it could suit you well.")

    assert score.rating >= 3
    assert "low_effort" not in score.signals


def test_stringing_magic_phrases_together_earns_nothing():
    score = score_seller_turn("help me understand what matters most tell me more what are you hoping")

    assert score.rating <= 3


def test_echoing_the_buyers_own_words_scores_highest():
    score = score_seller_turn(
        "What made the reliability of your current van start to matter so much?",
        buyer_message="My van keeps breaking down and reliability is everything to me",
        completed_turns=2,
    )

    assert score.rating == 5
    assert {"open_question", "mirroring"} <= set(score.signals)


def test_pitching_early_is_penalised_but_answering_a_price_question_is_not():
    unprompted = score_seller_turn(
        "Our finance package starts at 299 monthly.",
        buyer_message="Hi, just looking around",
        completed_turns=0,
    )
    answering = score_seller_turn(
        "Our finance package starts at 299 monthly.",
        buyer_message="So what would the monthly finance cost be?",
        completed_turns=0,
    )

    assert "premature_pitch" in unprompted.signals
    assert "premature_pitch" not in answering.signals
    assert answering.rating > unprompted.rating


def test_pressure_language_lowers_the_rating():
    score = score_seller_turn("You need to decide right now, this deal is today only.")

    assert score.rating < 3
    assert "pressure" in score.signals


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Sure.", "low_effort"),
        ("What is driving this? When do you need it? Who else decides? Why now?", "question_stacking"),
        ("word " * 120, "monologue"),
    ],
)
def test_shape_problems_are_flagged_by_name(message, expected):
    assert expected in score_seller_turn(message).signals


def test_every_fired_signal_carries_a_reason_for_the_learner():
    """The review shows why a turn was marked, so no signal may be silent."""
    score = score_seller_turn(
        "You need to decide right now.",
        buyer_message="I want to think about it",
    )

    assert score.signals
    assert len(score.reasons) == len(score.signals)
    assert all(reason.strip() for reason in score.reasons)


def test_config_weights_and_thresholds_are_all_present():
    cfg = load_selling_signals()
    weights, limits = cfg["weights"], cfg["thresholds"]

    assert set(weights) == {
        "open_question", "mirroring", "acknowledgement", "pressure",
        "premature_pitch", "question_stacking", "monologue", "low_effort",
    }
    assert set(limits) == {
        "low_effort_words", "monologue_words", "question_stacking_count",
        "mirroring_min_overlap", "discovery_turns",
    }
    # YAML reads bare on/no/yes as booleans - stopwords must stay text.
    assert all(isinstance(word, str) for word in cfg["mirroring_stopwords"])


def test_prospect_readiness_moves_on_selling_quality_and_records_why():
    session = ProspectSession(provider_type="dummy", product_type="general", difficulty="medium")
    session.conversation_history.append(
        {"role": "assistant", "content": "My van keeps breaking down and reliability matters"}
    )
    start = session.state.readiness
    session.state.turn_count = 3

    session._update_readiness("What made the reliability of your van start to matter so much?")

    assert session.state.readiness > start
    assert session.last_turn_score.rating == 5
    assert session.last_turn_score.reasons


def test_prospect_readiness_falls_when_the_seller_pressures():
    session = ProspectSession(provider_type="dummy", product_type="general", difficulty="medium")
    start = session.state.readiness
    session.state.turn_count = 3

    session._update_readiness("You need to decide right now, today only.")

    assert session.state.readiness < start
