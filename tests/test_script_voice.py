"""The AI port: the seller only calls named operations, so a fake voice drives it without prompts."""
import pytest

from core.loader import load_yaml
from core.script_engine.engine import ScriptState
from core.script_engine.listen import Heard
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.seller import ScriptSeller
from core.script_engine.voice import Voice

CFG = load_yaml("script/engine.yaml")
OFFER = load_offer("shay_coaching")


class FakeVoice:
    """Says what it is told to per operation and records each call: (name, first arg)."""

    def __init__(self, listen=None, ack="", answer=None, judge="vague"):
        self.said = {"listen": listen, "ack": ack, "answer": answer, "judge": judge}
        self.calls = []

    def new_turn(self):
        self.calls.append(("new_turn", None))

    def _op(name):
        def op(self, first, *rest):
            self.calls.append((name, first))
            return self.said[name]
        return op

    listen, ack, answer, judge = _op("listen"), _op("ack"), _op("answer"), _op("judge")


def seller(bow, voice, step="04"):
    s = ScriptSeller(CFG, load_method("cat"), OFFER, load_common_sense(), bow, voice)
    s.reset(ScriptState(step=step))
    return s


def test_a_heard_answer_is_acked_in_the_voices_words_and_moves_on(fake_embedder):
    voice = FakeVoice(listen=Heard(True, ack="Kids are a big reason."))
    s = seller(fake_embedder, voice)
    said, _ = s.reply("it's my kids")
    assert said.startswith("Kids are a big reason.") and s.state.step != "04"
    assert ("listen", "it's my kids") in voice.calls and not any(n == "ack" for n, _ in voice.calls)


def test_a_missed_answer_is_probed_in_the_voices_words_and_stays(fake_embedder):
    voice = FakeVoice(listen=Heard(False, probe="What about your kids drives that?"))
    s = seller(fake_embedder, voice)
    said, _ = s.reply("it's my kids")
    assert "What about your kids drives that?" in said and s.state.step == "04"


def test_every_turn_reopens_the_voice(fake_embedder):
    voice = FakeVoice(listen=Heard(True))
    s = seller(fake_embedder, voice)
    s.reply("it's my kids")
    s.reply("ok")
    assert [n for n, _ in voice.calls].count("new_turn") == 2


def test_one_failure_shuts_the_ai_for_the_rest_of_the_turn():
    sent = []

    def llm(prompt, max_tokens):
        sent.append(prompt)
        raise TimeoutError

    voice = Voice(CFG, OFFER, llm)
    with pytest.raises(TimeoutError):
        voice._ask("a", 5)
    with pytest.raises(RuntimeError):
        voice._ask("b", 5)
    voice.new_turn()
    with pytest.raises(TimeoutError):
        voice._ask("c", 5)
    assert sent == ["a", "c"]


def test_an_off_format_listen_also_shuts_the_turn():
    sent = []
    voice = Voice(CFG, OFFER, lambda p, n: sent.append(p) or "no idea what format you want")
    assert voice.listen("my kids", "Why", "Why now?", {}, False) is None
    calls = len(sent)
    assert voice.ack("my kids", "Why now?", {}, False) == "" and len(sent) == calls  # no second call
