"""Who is the rep, straight through roles.py: the counts behind the guess, the 'sure' line exactly at the
ratio, and role_of. Gaps found by mutation testing (the reading tests only saw the end result)."""

from core.calls.roles import FIRST_SPEAKER, MOST_QUESTIONS, NAMED, SpeakerStats, assign_roles, speaker_stats
from core.calls.transcript import Turn
from core.infra.loader import load_yaml

CFG = load_yaml("calls.yaml")
RATIO = CFG["rep"]["sure_ratio"]


def test_speaker_stats_counts_turns_words_and_questions_in_order_of_appearance():
    turns = [Turn("Rep", "Hi there. How are you?"), Turn("Buyer", "Fine thanks"), Turn("Rep", "What do you need?")]
    assert speaker_stats(turns, CFG) == [SpeakerStats("Rep", 2, 9, 2), SpeakerStats("Buyer", 1, 2, 0)]


def test_role_of_names_rep_prospect_and_anyone_else():
    roles = assign_roles([SpeakerStats("A", 3, 30, 4), SpeakerStats("B", 3, 40, 0), SpeakerStats("C", 1, 5, 0)], CFG)
    assert (roles.role_of("A"), roles.role_of("B"), roles.role_of("C")) == ("rep", "prospect", "other")


def test_sure_exactly_at_the_ratio_and_not_below():
    runner = 2
    at = assign_roles([SpeakerStats("A", 1, 10, round(RATIO * runner)), SpeakerStats("B", 1, 10, runner)], CFG)
    below = assign_roles([SpeakerStats("A", 1, 10, round(RATIO * runner) - 1), SpeakerStats("B", 1, 10, runner)], CFG)
    assert at.how == MOST_QUESTIONS and at.sure and not below.sure


def test_one_question_against_none_is_sure_only_if_the_ratio_allows():
    roles = assign_roles([SpeakerStats("A", 1, 10, 0), SpeakerStats("B", 1, 10, 1)], CFG)
    assert roles.rep == "B" and roles.sure == (1 >= RATIO)


def test_naming_the_rep_is_always_sure_and_the_prospect_talks_most():
    stats = [SpeakerStats("A", 1, 10, 9), SpeakerStats("Bo Lee", 1, 5, 0), SpeakerStats("C", 1, 50, 0)]
    roles = assign_roles(stats, CFG, named="bo")
    assert (roles.rep, roles.prospect, roles.how, roles.sure) == ("Bo Lee", "C", NAMED, True)


def test_no_questions_means_first_speaker_and_unsure():
    roles = assign_roles([SpeakerStats("A", 1, 1, 0), SpeakerStats("B", 1, 9, 0)], CFG)
    assert (roles.rep, roles.how, roles.sure) == ("A", FIRST_SPEAKER, False)
