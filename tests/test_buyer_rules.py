"""When the buyer says yes, walks, or keeps talking."""

import pytest

from core.buyer_rules import end_outcome

PATIENT = {"patience_turns": 10}


@pytest.mark.parametrize(
    "readiness, turns, max_turns, expected",
    [
        (0.85, 3, None, "sold"),      # keen enough, long enough
        (0.85, 2, None, None),        # keen but too early to close
        (0.5, 20, 20, "walked"),      # session turn limit hit
        (0.39, 10, None, "walked"),   # out of patience and still cold
        (0.4, 10, None, None),        # out of patience but warm enough to stay
        (0.0, 3, None, "walked"),     # lost all interest, after the grace turns
    ],
)
def test_end_outcome(readiness, turns, max_turns, expected):
    assert end_outcome(readiness, turns, PATIENT, max_turns) == expected
