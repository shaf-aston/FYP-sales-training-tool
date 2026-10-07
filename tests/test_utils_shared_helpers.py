"""The two helpers quiz.py and sell_evaluator.py used to each carry a copy of."""
from core.utils import merge_unique_items, tokenize


def test_tokenize_lowercases_and_keeps_apostrophes():
    assert tokenize("Don't STOP, 42 times!") == ["don't", "stop", "42", "times"]


def test_tokenize_survives_empty_and_none():
    assert tokenize("") == []
    assert tokenize(None) == []


def test_merge_drops_exact_duplicates_across_lists():
    merged = merge_unique_items(["Ask more", "Ask more"], ["Ask more"])

    assert merged == ["Ask more"]


def test_merge_treats_case_and_padding_as_the_same_item():
    merged = merge_unique_items(["Ask more"], ["  ask MORE  ", "Listen"])

    assert merged == ["Ask more", "Listen"]


def test_merge_drops_blanks_and_honours_the_cap():
    merged = merge_unique_items(["a", "", "  "], ["b", "c", "d"], max_items=3)

    assert merged == ["a", "b", "c"]


def test_earlier_lists_win_when_the_cap_trims():
    merged = merge_unique_items(["first"], ["second", "third", "fourth"], max_items=2)

    assert merged == ["first", "second"]
