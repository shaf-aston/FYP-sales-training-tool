"""Shrugs: what counts as saying nothing, and when their words are asked about."""
import pytest

from core.infra.loader import load_yaml
from core.buy_mode.script_engine.method import load_common_sense, load_method
from core.buy_mode.script_engine.hear.recognise import Listener
from core.buy_mode.script_engine.hear.shrug import Shrugs

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")


def shrugs(bow, fill=lambda t, slots: t.replace("{said|$|wanting to $}", slots["said"])):
    return Shrugs(CFG, load_common_sense(), Listener(CFG, bow), fill)


def test_filler_words_say_nothing_on_any_step(fake_embedder):
    assert shrugs(fake_embedder).says_nothing("ok", CAT.steps["01"], asking=False)


@pytest.mark.parametrize("said, nothing", [
    ("same", True), ("the usual", True), ("so basically ok", True), ("hi", True), ("hey, ok", True),   # round 51 callers: saved as the answer at every open step
    ("hi, more money", False), ("the usual stuff, my mortgage", False),   # guard: real words beside them
    ("ok well", True), ("omg!", True), ("well", True), ("actually ok", True),   # round 54 callers: saved as the answer at every open step
    ("yup", True), ("ngl ok", True), ("imo ok", True),   # round 56 callers: saved as the answer at every open step
    ("erm ok", True), ("uh ok", True), ("er", True), ("uhm", True), ("about that", True),   # round 57 callers: saved as the answer
    ("errm ok", True), ("er ok", True),   # round 57 mutation: no row had these
    ("erm, my mortgage", False),   # guard
    ("literally", True), ("personally", True), ("probably", True), ("perhaps", True), ("possibly", True),   # round 58 callers
    ("probably ok", True), ("literally ok", True),   # round 58 callers: saved as the answer
    ("perhaps money", False), ("personally my boss", False),   # guard
    ("tho", True), ("anyway", True), ("hopefully", True), ("ok tho", True), ("ok mainly", True), ("ok anyways", True),   # round 59 callers
    ("mainly money", False),   # guard
    ("obviously", True), ("lowkey", True), ("highkey", True), ("seriously", True), ("obviously ok", True), ("lowkey ok", True),   # round 60 callers
    ("lowkey money", False),   # guard
    ("true", True), ("essentially", True), ("usually", True), ("generally ok", True), ("essentially ok", True),   # round 61 callers
    ("true freedom", False),   # guard
    ("whatnot", True), ("innit", True), ("bruh", True), ("frankly ok", True), ("ok etc", True), ("bruh ok", True),   # round 62 callers
    ("frankly money", False),   # guard
    ("who knows", True), ("hard to say", True), ("beats me", True), ("we'll see", True), ("good question", True),   # round 64 callers
    ("who knows lol", True), ("it is what it is", True),
    ("hard to say, my family", False), ("we'll see more of the kids", False),   # guard: words beside them
    ("fingers crossed", True), ("touch wood", True), ("knock on wood", True), ("god willing", True),   # round 65 callers: saved as the answer
    ("up to you", True), ("you tell me", True), ("your call", True),   # round 65 callers: "up to you" at 05 was heard as leaving
    ("up to you to decide", False), ("you tell me the price", False),   # guard: words beside them
    ("your guess is as good as mine", True), ("though", True), ("mostly", True), ("ideally", True), ("ultimately", True), ("ok whatnot", True),   # round 65 mutation: no row had these
    ("hand on heart", True), ("if anything", True), ("per se", True), ("in all honesty", True), ("truth be told", True),   # round 66 callers: saved as the answer
    ("at a push", True), ("give or take", True), ("call it that", True), ("I'm easy", True), ("I don't mind", True), ("ok, to be fair", True),
    ("my boss, hand on heart", False), ("I don't mind the hours", False), ("call it fear", False), ("things like money", False),   # guard: words beside them
])
def test_round_51_words_alone_say_nothing(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["05"], asking=False) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("hand on heart", True), ("per se", True), ("I'm easy", True), ("in all honesty", True),   # round 66: kept at "Is there anything you've tried so far?"
    ("yes", False), ("yh", False), ("ok", False), ("yeah", False), ("👍", False), ("yes, hand on heart", False), ("no", False),   # guard: these answer it
    ("I suppose", False), ("a course", False),
    ("so, hand on heart", True), ("and if anything", True), ("but per se", True),   # a lead word beside it
    ("I am", False), ("it is", False), ("this", False), ("that's it", False), ("we are", False),   # guard: stop words answer "Are you...?"
])
def test_round_66_asked_as_yes_or_no_only_tags_say_nothing(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["06"], asking=False, closed=True) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("so to speak", True), ("as it were", True), ("you see", True), ("for what it's worth", True), ("tops", True),
    ("in a nutshell", True), ("at least", True), ("mind you", True), ("long story short", True), ("full stop", True),   # round 67: heard as "say that again", leaving, or a goal
    ("ok, so to speak", True), ("who knows", True),   # filler and shrug words beside them
    ("money so to speak", False), ("dunno man", False), ("freedom", False), ("tops up", False), ("my boss", False),   # guard: a word the labels must hear
])
def test_round_67_only_tags_say_nothing_where_labels_hear(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["01"], asking=False) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("if you ask me", True), ("all in all", True), ("by and large", True), ("in short", True), ("let's say", True),
    ("if you will", True), ("needless to say", True), ("believe it or not", True), ("as such", True),   # round 68: heard as "say that again", a worry, or a goal
    ("money as such", False), ("in short supply", False), ("once and for all", False), ("all of it", False),   # guard: a word the labels must hear
])
def test_round_68_only_tags_say_nothing_where_labels_hear(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["01"], asking=False) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("on the whole", True), ("for the most part", True), ("all things considered", True), ("at any rate", True), ("first and foremost", True), ("for starters", True),
    ("deep down", True), ("to some extent", True), ("as I see it", True), ("as far as I know", True), ("when all is said and done", True), ("admittedly", True), ("granted", True),   # round 69: heard as "say that again", a goal, or saved
    ("the whole family", False), ("deep down in debt", False), ("a good deal", False), ("money to some extent", False),   # guard: a word the labels must hear
])
def test_round_69_only_tags_say_nothing_where_labels_hear(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["01"], asking=False) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("in any case", True), ("simply put", True), ("as a matter of fact", True), ("in fact", True), ("in truth", True), ("on balance", True), ("in theory", True), ("in practice", True),
    ("at a guess", True), ("presumably", True), ("apparently", True), ("funnily enough", True), ("as it happens", True), ("by the way", True), ("btw", True), ("if that", True), ("at best", True),   # round 70: "if that" was "say that again" at every step
    ("the balance", False), ("in debt", False), ("best guess", False), ("money in theory", False),   # guard: a word the labels must hear
])
def test_round_70_only_tags_say_nothing_where_labels_hear(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["01"], asking=False) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("for the record", True), ("to be clear", True), ("in other words", True), ("that said", True), ("having said that", True), ("off the top of my head", True),
    ("roughly speaking", True), ("strictly speaking", True), ("technically", True), ("real talk", True), ("no lie", True), ("bottom line", True),
    ("and such", True), ("and the like", True), ("or so", True),   # round 71: "and such" was "say that again" at every step, "real talk" "I'm an AI"
    ("the record", False), ("bottom", False), ("talk", False), ("money technically", False),   # guard: a word the labels must hear
])
def test_round_71_only_tags_say_nothing_where_labels_hear(said, nothing, fake_embedder):
    assert shrugs(fake_embedder).says_nothing(said, CAT.steps["01"], asking=False) == nothing


@pytest.mark.parametrize("said, nothing", [
    ("who knows?", True), ("hard to say?", True), ("we'll see?", True), ("up to you?", True), ("you tell me?", True), ("lol who knows?", True),   # round 71 mutation: "I don't know that one offhand"
    ("no idea?", True), ("no clue?", True), ("search me?", True),
    ("so to speak?", True), ("by and large?", True), ("that said?", True), ("really?", True), ("lol, per se?", True),   # round 72: tags as a question got "I don't know that one offhand"
    ("how so?", False), ("really, how much?", False), ("really, why?", False), ("per se, what?", False), ("so to speak, money?", False),   # guard: words that ask, or an answer
    ("why?", False), ("is it up to you?", False), ("who knows, money?", False), ("who knows what?", False), ("what is your call?", False), ("not sure?", False),   # guard: a question, or more than the shrug
])
def test_a_question_that_is_only_a_shrug_says_nothing(said, nothing, fake_embedder):
    for step in ("05", "18"):
        assert shrugs(fake_embedder).says_nothing(said, CAT.steps[step], asking=True) == nothing, step


def test_round_67_asked_as_yes_or_no_without_a_catch_all_labels_still_decide(fake_embedder):
    assert not shrugs(fake_embedder).says_nothing("obviously", CAT.steps["01"], asking=False, closed=True)  # a yes to "jumping in?"


def test_shrug_words_say_nothing_only_where_a_catch_all_would_keep_them(fake_embedder):
    s = shrugs(fake_embedder)
    assert s.says_nothing("dunno man", CAT.steps["03"], asking=False)      # labels + catch-all
    assert not s.says_nothing("dunno man", CAT.steps["01"], asking=False)  # labels only: they decide


def test_a_question_is_never_a_shrug(fake_embedder):
    assert not shrugs(fake_embedder).says_nothing("no clue, what?", CAT.steps["04"], asking=True)


def test_ask_meaning_only_about_the_question_or_after_a_shrug(fake_embedder):
    s = shrugs(fake_embedder)
    q = "What do you want to achieve by making money online?"
    assert s.ask_meaning("I want money online", q, empty=False, heard_ahead=False).startswith("What do you mean")
    assert s.ask_meaning("hey there", q, empty=False, heard_ahead=False) == ""         # off topic
    assert s.ask_meaning("stuff I guess", q, empty=True, heard_ahead=False) != ""      # a shrug with words
    assert s.ask_meaning("dunno man", q, empty=True, heard_ahead=False) == ""          # nothing to ask about
    assert s.ask_meaning("I want money online", q, empty=False, heard_ahead=True) == ""  # clear, just early
    assert s.ask_meaning("what I said", q, empty=False, heard_ahead=False) == ""       # round 33: "what" is no topic
    assert s.ask_meaning("who knows", q, empty=True, heard_ahead=False) == ""          # round 64: was "What do you mean by who knows?"
    assert s.ask_meaning("hard to say", q, empty=True, heard_ahead=False) == ""
    assert s.ask_meaning("beats me", q, empty=True, heard_ahead=False) == ""
    assert s.ask_meaning("who knows, stuff", q, empty=True, heard_ahead=False) == "What do you mean by stuff?"   # round 65: was "...by who knows, stuff?"
    assert s.ask_meaning("good question, things", q, empty=True, heard_ahead=False) == "What do you mean by things?"
    assert s.ask_meaning("stuff, hard to say", q, empty=True, heard_ahead=False) == "What do you mean by stuff?"
    for said in ("not sure what to say", "I haven't thought about it", "I can't think of anything"):   # round 65 mutation: no row had these
        assert s.ask_meaning(said, q, empty=True, heard_ahead=False) == "", said


def test_an_answer_they_already_gave_is_never_asked_about(fake_embedder):
    """"More money" again after "What are you hoping to achieve with more money?": what they meant is known."""
    s = shrugs(fake_embedder)
    q = "What are you hoping to achieve with more money?"
    assert s.ask_meaning("More money", q, empty=True, heard_ahead=False, known=["more money"]) == ""
    assert s.ask_meaning("More money", q, empty=True, heard_ahead=False, known=["financial freedom"]) != ""


def test_ask_meaning_is_empty_when_their_words_cant_be_said_back(fake_embedder):
    s = shrugs(fake_embedder, fill=lambda t, slots: None)
    assert s.ask_meaning("stuff I guess", "Why?", empty=True, heard_ahead=False) == ""


def test_a_plain_no_is_only_no_words(fake_embedder):
    """Round 17: "nah" was heard as "what do you mean?"; a plain no is an answer, never an interruption."""
    s = shrugs(fake_embedder)
    assert all(s.plain_no(t) for t in ("nah", "nope", "no", "no no", "nah."))
    assert not any(s.plain_no(t) for t in ("nah not really", "no idea", "ok", "", "the"))
    assert not s.plain_no("no thanks")   # thanks counts only when they say so (a yes-or-no question asked)
