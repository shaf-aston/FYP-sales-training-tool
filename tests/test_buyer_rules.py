"""When the buyer says yes, walks, or keeps talking."""

import pytest

from core.buyer_rules import end_outcome

PATIENT = {"patience_turns": 10}


@pytest.mark.parametrize(
    "readiness, turns, expected",
    [
        (0.85, 3, "sold"),      # keen enough, long enough
        (0.85, 2, None),        # keen but too early to close
        (0.39, 10, "walked"),   # out of patience and still cold
        (0.4, 10, None),        # out of patience but warm enough to stay
        (0.0, 3, "walked"),     # lost all interest, after the grace turns
        (0.0, 1, None),         # one weak opener is not a lost sale
    ],
)
def test_end_outcome(readiness, turns, expected):
    assert end_outcome(readiness, turns, PATIENT) == expected
