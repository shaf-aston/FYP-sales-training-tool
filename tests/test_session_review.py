"""The session review is recomputed from the transcript, never stored: per-turn ratings
differ by what the seller said, and praise must be earned."""

from pathlib import Path

import pytest

from core.buyer_session import BuyerSession
from core.loader import load_buyer_config
from core.session_review import build_review, pick_pivotal_turns

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def behaviour():
    return load_buyer_config()["difficulty_profiles"]["medium"]["behaviour"]


@pytest.fixture
def transcript():
    """A session with one premature pitch, one good question, and one pushy turn."""
    return [
        {"role": "assistant", "content": "Just having a look. My old van keeps breaking down."},
        {"role": "user", "content": "Our finance package starts at 299 monthly."},
        {"role": "assistant", "content": "That isn't really what I asked about."},
        {"role": "user", "content": "What made the reliability of your van start to matter so much?"},
        {"role": "assistant", "content": "I lost two days of work waiting for a recovery truck."},
        {"role": "user", "content": "You need to decide right now, today only."},
        {"role": "assistant", "content": "I don't like being rushed."},
    ]


def test_every_seller_turn_is_annotated_with_its_evidence(behaviour, transcript):
    review = build_review(transcript, behaviour)

    assert [t["turn"] for t in review["turns"]] == [1, 2, 3]
    assert review["summary"]["turn_count"] == 3
    for turn in review["turns"]:
        assert 1 <= turn["rating"] <= 5
        assert len(turn["reasons"]) == len(turn["signals"])


def test_the_pivotal_turns_are_the_ones_that_cost_ground(behaviour, transcript):
    review = build_review(transcript, behaviour)

    # Turn 1 pitched before discovery, turn 3 pressured. Turn 2 went well.
    assert review["pivotal_turns"] == [1, 3]


def test_a_session_that_went_well_offers_nothing_to_redo(behaviour):
    strong = [
        {"role": "assistant", "content": "My van keeps breaking down and reliability matters."},
        {"role": "user", "content": "What made the reliability of your van start to matter?"},
        {"role": "assistant", "content": "I lost two days of work."},
        {"role": "user", "content": "Tell me what losing those two days of work actually cost you."},
        {"role": "assistant", "content": "About 600 pounds."},
    ]

    assert pick_pivotal_turns(build_review(strong, behaviour)["turns"]) == []


def test_the_readiness_curve_starts_at_the_difficulty_and_tracks_every_turn(behaviour, transcript):
    review = build_review(transcript, behaviour)

    assert review["readiness_curve"][0] == round(behaviour["initial_readiness"], 3)
    assert len(review["readiness_curve"]) == len(review["turns"]) + 1
    assert review["readiness_curve"][-1] == review["turns"][-1]["readiness_after"]


def test_an_unanswered_last_turn_is_still_reviewed(behaviour):
    review = build_review(
        [{"role": "user", "content": "So what do you think?"}], behaviour
    )

    assert review["summary"]["turn_count"] == 1
    assert review["turns"][0]["buyer"] == ""


def test_an_empty_session_reviews_without_crashing(behaviour):
    review = build_review([], behaviour)

    assert review["turns"] == []
    assert review["pivotal_turns"] == []
    assert review["summary"]["turn_count"] == 0


def test_replayed_readiness_matches_what_the_learner_saw_live(behaviour, transcript):
    """A review that disagreed with the live session would be worse than none."""
    session = BuyerSession(provider_type="dummy", product_type="general", difficulty="medium")
    session.conversation_history.append(transcript[0])

    for entry in transcript[1:]:
        if entry["role"] == "user":
            session.state.turn_count += 1
            session.conversation_history.append(entry)
            session._update_readiness(entry["content"])
        else:
            session.conversation_history.append(entry)

    review = build_review(transcript, behaviour)
    assert round(session.state.readiness, 3) == review["readiness_curve"][-1]


def test_rewinding_restores_the_buyer_to_that_exact_point(behaviour, transcript):
    session = BuyerSession(provider_type="dummy", product_type="general", difficulty="medium")
    session.conversation_history = list(transcript)
    session.state.turn_count = 3
    session.state.has_walked = True

    assert session.rewind_to_turn(3) is True

    # Turn 3 and everything after it is gone; the learner says it again.
    assert [e["role"] for e in session.conversation_history] == [
        "assistant", "user", "assistant", "user", "assistant",
    ]
    assert session.state.turn_count == 2
    assert session.state.has_walked is False
    assert session.state.readiness == build_review(
        session.conversation_history, behaviour
    )["readiness_curve"][-1]


def test_rewinding_to_a_turn_that_never_happened_is_refused(transcript):
    session = BuyerSession(provider_type="dummy", product_type="general", difficulty="medium")
    session.conversation_history = list(transcript)

    assert session.rewind_to_turn(9) is False
    assert session.rewind_to_turn(0) is False
    assert len(session.conversation_history) == len(transcript)


def test_only_the_worst_turns_are_offered_for_a_redo():
    """More costly turns than slots: the learner is pointed at the worst ones."""
    turns = [
        {"turn": 1, "rating": 2, "readiness_change": -0.05},
        {"turn": 2, "rating": 1, "readiness_change": -0.20},
        {"turn": 3, "rating": 2, "readiness_change": -0.16},
        {"turn": 4, "rating": 1, "readiness_change": -0.30},
        {"turn": 5, "rating": 5, "readiness_change": 0.16},
    ]

    assert pick_pivotal_turns(turns, count=3) == [2, 3, 4]


def test_when_two_turns_cost_the_same_the_weaker_one_is_picked_first():
    turns = [
        {"turn": 1, "rating": 4, "readiness_change": -0.10},
        {"turn": 2, "rating": 1, "readiness_change": -0.10},
    ]

    assert pick_pivotal_turns(turns, count=1) == [2]


def test_a_strong_discovery_question_and_a_price_first_line_are_rated_differently(behaviour):
    session = [
        {"role": "assistant", "content": "Just having a look. My old van keeps breaking down."},
        {"role": "user", "content": "What made the reliability of your old van start to matter so much?"},
        {"role": "assistant", "content": "I lost two days of work."},
        {"role": "user", "content": "Our finance package is 299 monthly, what do you think?"},
        {"role": "assistant", "content": "Hmm."},
    ]

    first, second = build_review(session, behaviour)["turns"]

    assert first["rating"] > second["rating"]
    assert first["readiness_change"] > second["readiness_change"]
    assert first["reasons"] != second["reasons"]


def test_stock_and_yes_no_questions_earn_less_than_one_built_on_their_words(behaviour):
    buyer = {"role": "assistant", "content": "My old van keeps breaking down."}
    ratings = []
    for line in ("How are you today?", "Do you want a new van?", "What happens when the van breaks down?"):
        review = build_review([buyer, {"role": "user", "content": line}], behaviour)
        ratings.append(review["turns"][0]["rating"])

    assert ratings[2] > ratings[0] and ratings[2] > ratings[1]


def test_a_weak_session_is_never_praised_and_says_what_to_work_on(behaviour):
    weak = [
        {"role": "assistant", "content": "Just looking."},
        {"role": "user", "content": "ok sure"},
        {"role": "assistant", "content": "Right."},
        {"role": "user", "content": "fine then"},
        {"role": "assistant", "content": "Mm."},
    ]

    summary = build_review(weak, behaviour)["summary"]

    assert summary["went_well"] is False
    assert summary["work_on"]


def test_a_strong_session_is_allowed_praise(behaviour):
    strong = [
        {"role": "assistant", "content": "My van keeps breaking down and reliability matters."},
        {"role": "user", "content": "What made the reliability of your van start to matter?"},
        {"role": "assistant", "content": "I lost two days of work."},
        {"role": "user", "content": "Tell me what losing those two days of work actually cost you."},
        {"role": "assistant", "content": "About 600 pounds."},
    ]

    assert build_review(strong, behaviour)["summary"]["went_well"] is True


def test_the_review_page_praises_only_a_passing_grade():
    # Found by name, so renaming its feature folder does not break this test.
    [dialog] = (ROOT / "web" / "src" / "features").glob("*/ReviewDialog.tsx")
    tsx = dialog.read_text(encoding="utf8")

    assert "summary.went_well" in tsx and 'gradeTone(grade) !== "danger"' in tsx
