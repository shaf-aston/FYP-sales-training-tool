"""Shrugs: what counts as saying nothing, and when their words are asked about."""
from core.loader import load_yaml
from core.script_engine.method import load_common_sense, load_method
from core.script_engine.recognise import Listener
from core.script_engine.shrug import Shrugs

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")


def shrugs(bow, fill=lambda t, slots: t.replace("{said|$|wanting to $}", slots["said"])):
    return Shrugs(CFG, load_common_sense(), Listener(CFG, bow), fill)


def test_filler_words_say_nothing_on_any_step(fake_embedder):
    assert shrugs(fake_embedder).says_nothing("ok", CAT.steps["01"], asking=False)


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


def test_an_answer_they_already_gave_is_never_asked_about(fake_embedder):
    """"More money" again after "What are you hoping to achieve with more money?": what they meant is known."""
    s = shrugs(fake_embedder)
    q = "What are you hoping to achieve with more money?"
    assert s.ask_meaning("More money", q, empty=True, heard_ahead=False, known=["more money"]) == ""
    assert s.ask_meaning("More money", q, empty=True, heard_ahead=False, known=["financial freedom"]) != ""


def test_ask_meaning_is_empty_when_their_words_cant_be_said_back(fake_embedder):
    s = shrugs(fake_embedder, fill=lambda t, slots: None)
    assert s.ask_meaning("stuff I guess", "Why?", empty=True, heard_ahead=False) == ""
