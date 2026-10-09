"""Per-turn ratings must differ by what the seller said, and praise must be earned."""

from pathlib import Path

import pytest

from core.loader import load_buyer_config
from core.session_review import build_review

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def behaviour():
    return load_buyer_config()["difficulty_profiles"]["medium"]["behaviour"]


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

    assert "summary.went_well" in tsx and '["D", "F"]' in tsx
