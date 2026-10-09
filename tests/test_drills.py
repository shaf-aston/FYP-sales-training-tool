"""Recall drills: the blank must cover the move, and reveal must match."""

import pytest

from core.drills import (
    OWN_LINE_GROUP,
    build_drill_set,
    drills_from_own_turns,
    group_summaries,
    load_drills,
    split_blanks,
)


@pytest.mark.parametrize(
    "line, segments, answers",
    [
        ("Before I ask, [tell me why].", ["Before I ask, ", "."], ["tell me why"]),
        ("[Fair enough], I moved too fast.", ["", ", I moved too fast."], ["Fair enough"]),
        ("Two [blanks] in one [line].", ["Two ", " in one ", "."], ["blanks", "line"]),
        ("No blank here.", ["No blank here."], []),
    ],
)
def test_a_line_splits_into_visible_parts_and_hidden_answers(line, segments, answers):
    assert split_blanks(line) == (segments, answers)


def test_segments_and_answers_always_interleave():
    """The screen renders segment, blank, segment - so there is always one more
    segment than answer, or the line comes out scrambled."""
    for drill in load_drills():
        assert len(drill.segments) == len(drill.answers) + 1


def test_rebuilding_a_drill_gives_back_a_readable_sentence():
    for drill in load_drills():
        rebuilt = "".join(
            segment + (drill.answers[i] if i < len(drill.answers) else "")
            for i, segment in enumerate(drill.segments)
        )
        assert rebuilt.strip()
        assert "[" not in rebuilt and "]" not in rebuilt


def test_every_authored_line_actually_hides_something():
    drills = load_drills()

    assert drills
    assert all(drill.answers for drill in drills)
    # A blank that hides one short word trains recognition, not recall.
    assert all(any(len(a.split()) >= 2 for a in drill.answers) for drill in drills)


def test_every_group_explains_why_it_matters():
    groups = group_summaries()

    assert groups
    for group in groups:
        assert group["id"] and group["label"] and group["why"]


def test_drill_ids_are_unique():
    ids = [drill.id for drill in load_drills()]

    assert len(ids) == len(set(ids))


def test_your_own_strongest_turns_become_drills():
    turns = [
        {"turn": 1, "rating": 2, "seller": "You need to decide right now, today only."},
        {"turn": 2, "rating": 5, "seller": "Walk me through what a bad week looks like for your team."},
        {"turn": 3, "rating": 4, "seller": "Tell me what that delay actually cost you last month."},
    ]

    drills = drills_from_own_turns(turns)

    assert [d.group for d in drills] == [OWN_LINE_GROUP, OWN_LINE_GROUP]
    assert all(d.source == "own_turn" for d in drills)
    # The weak turn is not worth memorising.
    assert not any("decide right now" in "".join(d.segments) for d in drills)


def test_a_turn_too_short_to_split_is_skipped():
    assert drills_from_own_turns([{"turn": 1, "rating": 5, "seller": "Tell me more."}]) == []


def test_your_own_lines_come_first_and_get_their_own_group():
    result = build_drill_set(
        [{"turn": 1, "rating": 5, "seller": "Walk me through what a bad week looks like here."}]
    )

    assert result["groups"][0]["id"] == OWN_LINE_GROUP
    assert result["drills"][0]["source"] == "own_turn"


def test_without_a_session_only_the_authored_lines_show():
    result = build_drill_set([])

    assert OWN_LINE_GROUP not in [g["id"] for g in result["groups"]]
    assert all(d["source"] == "authored" for d in result["drills"])


def test_a_line_too_short_to_split_costs_the_next_best_line_its_place():
    """Skipping must not silently shrink the deck - it should fall through to the
    learner's next strongest line instead."""
    turns = [
        {"turn": 1, "rating": 5, "seller": "Tell me more."},  # too short to split
        {"turn": 2, "rating": 5, "seller": "Walk me through what a bad week looks like."},
        {"turn": 3, "rating": 5, "seller": "Tell me what that delay actually cost you."},
        {"turn": 4, "rating": 4, "seller": "What made that start to matter to you now?"},
        {"turn": 5, "rating": 4, "seller": "Which of those would you fix first, and why?"},
    ]

    drills = drills_from_own_turns(turns, limit=3)

    assert len(drills) == 3
    assert not any("Tell me more" in "".join(d.segments) for d in drills)


def test_only_the_strongest_lines_make_the_cut():
    turns = [
        {"turn": n, "rating": 5 if n <= 2 else 4,
         "seller": f"Walk me through what problem number {n} actually costs you."}
        for n in range(1, 6)
    ]

    drills = drills_from_own_turns(turns, limit=2)

    assert len(drills) == 2
    assert [d.id for d in drills] == [f"{OWN_LINE_GROUP}:1", f"{OWN_LINE_GROUP}:2"]
