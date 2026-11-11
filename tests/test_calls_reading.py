"""Who the rep is, and the prospect's profile, from a whole call (config/calls_sample.txt and small calls)."""
import pytest

from core.calls.errors import CALL_TOO_LONG, CALL_TOO_SHORT, CALL_UNREADABLE, UNKNOWN_SPEAKER, CallError
from core.calls.reader import load_calls_config, read_call
from core.calls.roles import FIRST_SPEAKER, MOST_QUESTIONS, NAMED
from core.infra.loader import CONFIG_DIR

SAMPLE = (CONFIG_DIR / "calls_sample.txt").read_text("utf-8")


def call(*lines: str) -> str:
    return "\n".join(lines)


def test_the_rep_is_the_one_asking_questions():
    reading = read_call(SAMPLE)
    assert (reading.roles.rep, reading.roles.prospect) == ("Sarah Khan", "Dan Price")
    assert reading.roles.how == MOST_QUESTIONS and reading.roles.sure


def test_the_learner_can_say_who_they_are_by_first_name():
    reading = read_call(SAMPLE, rep="dan")
    assert (reading.roles.rep, reading.roles.prospect, reading.roles.how) == ("Dan Price", "Sarah Khan", NAMED)


def test_a_rep_who_never_speaks_is_refused():
    with pytest.raises(CallError) as caught:
        read_call(SAMPLE, rep="Priya")
    assert caught.value.code == UNKNOWN_SPEAKER


def test_with_no_questions_the_first_speaker_is_a_guess_to_check():
    reading = read_call(call("A: Hello.", "B: Hi.", "A: Nice day.", "B: It is."))
    assert reading.roles.rep == "A" and reading.roles.how == FIRST_SPEAKER and not reading.roles.sure


def test_a_close_question_count_is_not_sure():
    reading = read_call(call("A: How are you?", "B: Fine, and you?", "A: Good. What brings you here?", "B: Why do you ask?"))
    assert not reading.roles.sure


def test_the_profile_keeps_their_own_words():
    profile = read_call(SAMPLE).profile
    assert profile.name == "Dan"
    assert profile.background == "I run a small marketing agency, about six of us."
    assert profile.budget == "We've got maybe £3k set aside for training this quarter."   # not the £10k revenue goal
    assert "I need to build a sales process the team can run without me." in profile.needs
    assert any("wasting most evenings" in p for p in profile.pain_points)
    assert [o["type"] for o in profile.objections] == ["price", "skepticism", "partner", "timing"]
    assert profile.objections[0]["text"] == "That's more than I budgeted for, to be honest."


def test_the_same_call_always_gives_the_same_profile():
    assert read_call(SAMPLE).to_json() == read_call(SAMPLE).to_json()


def test_every_profile_field_says_where_it_came_from():
    evidence = read_call(SAMPLE).profile.evidence
    assert evidence["budget"] == ["£3k"]
    assert evidence["difficulty"][0] == "4 objection(s)"


def test_an_anonymous_speaker_gets_a_plain_name():
    reading = read_call(call("Speaker 1: What do you need?", "Speaker 2: Not sure.", "Speaker 1: Why now?", "Speaker 2: No idea."))
    assert reading.profile.name == "Prospect"


def test_a_brief_pushy_buyer_reads_as_hard():
    reading = read_call(call(
        "Rep: What made you take the call?", "Buyer: No idea. Too expensive anyway.",
        "Rep: What would help?", "Buyer: Not interested really.",
        "Rep: Can I ask why?", "Buyer: We already have a tool. Is this a scam?",
    ))
    assert reading.profile.difficulty == "hard"
    assert reading.profile.personality.startswith("Gives short answers")


def test_history_puts_the_rep_on_the_learner_side():
    history = read_call(SAMPLE).history()
    assert history[0] == {"role": "user", "content": SAMPLE.split("\n")[4]}
    assert {h["role"] for h in history} == {"user", "assistant"}


@pytest.mark.parametrize("text, code", [
    ("just some words with no speakers at all", CALL_UNREADABLE),
    (call("WEBVTT", "", "00:00:01.000 --> 00:00:02.000", "<v A>Hi?", "", "00:00:03.000 --> 00:00:04.000", "<v B>Hello.",
          "", "00:00:05.000 --> 00:00:06.000", "<v A>Bye?"), CALL_TOO_SHORT),
])
def test_unusable_text_says_why(text, code):
    with pytest.raises(CallError) as caught:
        read_call(text)
    assert caught.value.code == code


def test_too_long_is_refused_before_reading():
    cfg = load_calls_config()
    cfg["limits"]["max_chars"] = 10
    with pytest.raises(CallError) as caught:
        read_call(SAMPLE, cfg=cfg)
    assert caught.value.code == CALL_TOO_LONG
