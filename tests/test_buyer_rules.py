"""When the buyer says yes, walks, or keeps talking."""

import pytest

from core.sell_mode.buyer_rules import end_outcome

PATIENT = {"patience_turns": 10}


@pytest.mark.parametrize(
    "readiness, turns, asked, expected",
    [
        (0.85, 3, True, "sold"),      # keen enough, long enough, and asked
        (0.85, 3, False, None),       # keen, but nobody asked for the sale yet
        (0.85, 2, True, None),        # keen but too early to close
        (0.39, 10, False, "walked"),  # out of patience and still cold
        (0.4, 10, False, None),       # out of patience but warm enough to stay
        (0.0, 3, False, "walked"),    # lost all interest, after the grace turns
        (0.0, 1, False, None),        # one weak opener is not a lost sale
    ],
)
def test_end_outcome(readiness, turns, asked, expected):
    assert end_outcome(readiness, turns, PATIENT, asked) == expected
