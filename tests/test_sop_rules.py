"""SOP adherence and checklist rules on their own, with a topic embedder (cosine 1 for the same topic, 0 otherwise),
so each rule is pinned without the meaning model. Gaps found by mutation testing."""

from core.infra.loader import load_yaml
from core.sop.adherence import _action, check_call
from core.sop.checklist import check_elements
from core.sop.outline import Stage

import re

CFG = load_yaml("sop.yaml")
TOPICS = ["decide", "budget", "follow"]


def embed(texts):
    return [[1.0 if t in text.lower() else 0.0 for t in TOPICS] + [0.001] for text in texts]


def test_no_steps_scores_zero():
    assert check_call([], ["Who decides?"], CFG, embed).score == 0


def test_a_short_question_carries_a_step_and_a_short_statement_does_not():
    stages = [Stage("Qualify", ["Ask who decides"])]
    assert check_call(stages, ["Who decides?"], CFG, embed).steps[0].done
    assert not check_call(stages, ["Decide, ok."], CFG, embed).steps[0].done   # under evidence_min_words, no "?"


def test_a_condition_with_no_action_keeps_the_whole_step():
    cond = re.compile(CFG["condition"], re.IGNORECASE)
    assert _action("If they push back on budget, ask what budget they had in mind", cond) == (
        "ask what budget they had in mind", True)
    assert _action("If they say no, ", cond) == ("If they say no, ", True)
    assert _action("Ask about budget", cond) == ("Ask about budget", False)


def test_an_untriggered_conditional_step_does_not_lower_the_score():
    stages = [Stage("Close", ["Ask who decides", "If they hesitate, offer a follow up call"])]
    result = check_call(stages, ["So who decides on this one?"], CFG, embed)
    assert result.score == 100 and [s.done for s in result.steps] == [True, False]


def test_the_most_specific_step_is_the_evidence_and_the_first_wins_a_tie():
    # "pain" by its cue words; the agenda step also says "goals", so it covers two elements: less specific
    broad, specific, tie = "Set the agenda and ask about their problems and goals", "Ask about their problems", \
        "Dig into their frustrations"
    got = {r.id: r for r in check_elements([Stage("S", [broad, specific, tie])], CFG, embed)}
    assert got["pain"].covered and got["pain"].step == specific
