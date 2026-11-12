"""An SOP step as the rep says it (core/sop/spoken.py): "Ask what they want" -> "What do you want?"."""
import pytest

from core.sop.spoken import as_question


@pytest.mark.parametrize("step, said", [
    ("Ask what made them book the call", "What made you book the call?"),
    ("Ask what they want to achieve in the next 12 months", "What do you want to achieve in the next 12 months?"),
    ("Find out what's getting in the way and how long it has been a problem",
     "What's getting in the way and how long has it been a problem?"),
    ("Ask who else is involved in the decision and what budget they have set aside",
     "Who else is involved in the decision and what budget have you set aside?"),
    ("Ask what specifically they need to think through", "What specifically do you need to think through?"),
    ("Ask them directly if they want to go ahead", "Do you want to go ahead?"),
    ("Ask if they're ready to start", "Are you ready to start?"),
    ("Ask whether they have tried a coach before", "Have you tried a coach before?"),
    ("Confirm whether they are the decision maker", "Are you the decision maker?"),
    ("Ask the prospect what their biggest challenge is", "What is your biggest challenge?"),
    ("Ask what their goals are for next year", "What are your goals for next year?"),
    ("Ask how they found us", "How did you find us?"),
    ("Ask when they decided to look for help", "When did you decide to look for help?"),
    ("Ask where they see themselves in a year", "Where do you see yourself in a year?"),
    ("Ask how much they would need to make each month", "How much would you need to make each month?"),
    ("Understand what is stopping them.", "What is stopping you?"),
])
def test_a_step_that_asks_is_said_as_a_question(step, said):
    assert as_question(step) == said


@pytest.mark.parametrize("step", [
    "Thank them for their time and confirm they have 30 minutes",   # asks nothing
    "Recap their goals in their own words",
    'Ask: "What made you book?"',          # already says its question: the caller keeps it as written
    "Ask if it all makes sense",           # no safe question order
    "Ask what they reconsidered",          # a past tense with no known plain form
    "",
])
def test_a_step_that_asks_nothing_we_can_word_gives_none(step):
    assert as_question(step) is None
