"""Tests that close gaps found by mutation testing: small code changes (`<` -> `<=`, `*` -> `/`, `and` -> `or`)
that the rest of the suite let through."""

import pytest

from core.infra.similarity import best_pairs, similarity
from core.training.drills import _split_point, drills_from_own_turns
from core.training.turn_rating import (
    _is_closed_question,
    _is_stock,
    _mirrored_words,
    load_turn_rating,
    rate_turn,
    readiness_delta,
)


# --- similarity -----------------------------------------------------------------------------------------------

def _fake_embed(table):
    return lambda texts: [table[t] for t in texts]


def test_similarity_is_cosine_of_unit_vectors():
    embed = _fake_embed({"a": [3.0, 0.0], "b": [0.0, 5.0], "c": [2.0, 2.0], "d": [-4.0, 0.0]})
    s = similarity(["a"], ["b", "c", "d", "a"], embed)
    assert s[0][0] == pytest.approx(0.0)
    assert s[0][1] == pytest.approx(2 ** -0.5)
    assert s[0][2] == pytest.approx(-1.0)
    assert s[0][3] == pytest.approx(1.0)


def test_similarity_zero_vector_does_not_divide_by_zero():
    s = similarity(["z"], ["a"], _fake_embed({"z": [0.0, 0.0], "a": [1.0, 0.0]}))
    assert s == [[0.0]]


def test_similarity_empty_side_gives_one_empty_row_per_row():
    def never(_):
        raise AssertionError("embed must not be called")

    assert similarity(["x", "y"], [], never) == [[], []]
    assert similarity([], ["x"], never) == []


def test_best_pairs_is_one_to_one_strongest_first_and_bar_inclusive():
    scores = [[0.9, 0.8], [0.95, 0.5], [0.1, 0.5]]
    # row 1 takes col 0 (0.95), row 0 falls back to col 1, row 2's 0.5 sits exactly on the bar but col 1 is used
    assert best_pairs(scores, 0.5) == {1: 0, 0: 1}
    assert best_pairs([[0.5]], 0.5) == {0: 0}
    assert best_pairs([[0.49]], 0.5) == {}


# --- readiness_delta --------------------------------------------------------------------------------------------

BEHAVIOUR = {"readiness_gain_per_good_turn": 0.1, "readiness_loss_per_bad_turn": 0.2,
             "readiness_drift_per_neutral_turn": 0.01}


@pytest.mark.parametrize("rating, expected", [(5, 0.2), (4, 0.1), (3, 0.01), (2, -0.2), (1, -0.4)])
def test_readiness_delta_per_rating(rating, expected):
    assert readiness_delta(rating, BEHAVIOUR) == pytest.approx(expected)


# --- rate_turn thresholds ---------------------------------------------------------------------------------------

LIMITS = load_turn_rating()["thresholds"]


def test_monologue_starts_only_above_the_limit():
    at = " ".join(["word"] * LIMITS["monologue_words"])
    assert "monologue" not in rate_turn(at).signals
    assert "monologue" in rate_turn(at + " more").signals


def test_low_effort_only_below_the_limit():
    at = " ".join(["word"] * LIMITS["low_effort_words"])
    short = " ".join(["word"] * (LIMITS["low_effort_words"] - 1))
    assert "low_effort" not in rate_turn(at).signals
    assert "low_effort" in rate_turn(short).signals


def test_premature_pitch_only_before_discovery_turns():
    line = "Let me tell you about the price of our package today."
    assert "premature_pitch" in rate_turn(line, completed_turns=LIMITS["discovery_turns"] - 1).signals
    assert "premature_pitch" not in rate_turn(line, completed_turns=LIMITS["discovery_turns"]).signals
    assert "premature_pitch" in rate_turn(line).signals  # default: no turns done yet


def test_rating_is_clamped_to_one_and_five():
    bad = "Buy now, price drops, last chance, limited offer, discount ends today, act now"
    assert 1 <= rate_turn(bad).rating <= 5
    good = rate_turn("I hear you, the admin is eating your evenings. What does the admin look like on a bad week?",
                     buyer_message="The admin is eating my evenings every week")
    assert good.rating == 5


def test_neutral_turn_scores_the_neutral_rating():
    assert rate_turn("We ship the parcels out on Tuesdays.").rating == LIMITS["neutral_rating"]


# --- helpers ---------------------------------------------------------------------------------------------------

def test_mirrored_words_needs_long_non_stopwords_on_both_sides():
    assert _mirrored_words("the admin costs", "the admin is slow", ["the"]) == ["admin"]
    assert _mirrored_words("we go", "we go", []) == []          # words of 2 letters never count
    assert _mirrored_words("our team", "our team", ["team"]) == ["our"]  # stopword dropped on both sides


def test_stock_question_allows_at_most_three_tail_words():
    stock = ["how are you"]
    assert _is_stock("how are you doing today then", stock)
    assert not _is_stock("how are you doing today then mate", stock)


def test_closed_question_after_a_lead_word():
    cfg = load_turn_rating()
    qw, starters = cfg.get("question_words", []), cfg.get("closed_starters", [])
    assert _is_closed_question("So shall I send it?", qw, starters)
    assert _is_closed_question("Shall I send it?", qw, starters)


# --- drills ----------------------------------------------------------------------------------------------------

def test_split_point_halves_and_respects_min_words():
    assert _split_point("one two three four five six", 6) == ("one two three ", "four five six")
    assert _split_point("one two three four five", 6) is None


def test_own_turn_drills_rank_by_rating_then_turn_and_skip_missing_rating():
    line = "what does a normal week look like for you"
    turns = [{"turn": 3, "rating": 4, "seller": line}, {"turn": 1, "rating": 5, "seller": line},
             {"turn": 2, "rating": 4, "seller": line}, {"turn": 9, "seller": line}]
    ids = [d.id.split(":")[-1] for d in drills_from_own_turns(turns, limit=5)]
    assert ids == ["1", "2", "3"]


# --- embedder disk cache ---------------------------------------------------------------------------------------

def test_embedder_keeps_warmed_lines_on_disk_and_reads_them_back(tmp_path):
    from core.infra.embedder import FastEmbedEmbedder

    def made(calls):
        e = object.__new__(FastEmbedEmbedder)
        e._file, e._batch_size = tmp_path / "seen-m.npz", 8
        e._compute = lambda texts: calls.extend(texts) or [[float(len(t)), 1.0] for t in texts]
        e._seen = e._load()
        return e

    first = []
    made(first).warm(["hi", "hello there"])
    assert first == ["hi", "hello there"]
    again = []
    e = made(again)                            # a restart: nothing embedded again
    e.warm(["hi", "hello there"])
    assert again == [] and e.embed(["hello there"]) == [[11.0, 1.0]]
    (tmp_path / "seen-m.npz").write_bytes(b"broken")
    assert made([])._seen == {}                # a broken file is ignored, never a crash
