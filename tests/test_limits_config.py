"""config/limits.yaml is a trust boundary: every number must be > 0."""

import pytest

from core import constants


def test_limits_file_loads_and_names_resolve():
    assert constants.LLM["buyer_reply"]["max_tokens"] > 0
    assert constants.RATE_LIMITS["buy_chat"] == (60, 60)
    assert len(constants.GRADE_LABELS) == len(constants.GRADE_THRESHOLDS) + 1


@pytest.mark.parametrize("bad", [0, -1, {"a": {"b": 0}}, [1, -0.5]])
def test_zero_or_negative_is_rejected(bad):
    with pytest.raises(ValueError):
        constants._check_positive(bad)


def test_booleans_and_strings_pass():
    constants._check_positive({"flag": False, "label": "A", "n": 1})
