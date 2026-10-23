"""Edge cases found by mutation testing: limits, index guards and logs that no other test pinned down."""
import io
import logging
import wave
from pathlib import Path

from core.loader import load_yaml
from core.providers import speech
from core.script_engine.checks import CheckContext, check, clip
from core.script_engine.engine import ScriptState, asked_line, object_to
from core.script_engine.listen import hear, parse
from core.script_engine.method import load_method

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")
MINI = load_method("mini", *[Path(__file__).parent / "fixtures" / "script_engine"] * 2)


def ctx(**kw):
    base = {"max_words": 30, "questions": 1, "price_ok": False, "price": "$5k",
            "banned_phrases": tuple(CFG["banned_phrases"])}
    return CheckContext(**{**base, **kw})


# listen
def test_listen_tidy():
    assert parse("ANSWERED: no\nPROBE: n/a") == (False, "", "")
    assert parse("ANSWERED: no\nPROBE: `Why not?`") == (False, "", "Why not?")


def test_listen_logs(caplog):
    probe_ctx = ctx(questions=1)
    ack_ctx = ctx(questions=0)
    def h(raw, asked="What holds you back?"):
        return hear(lambda p, n: raw, "p", 90, ack_ctx, probe_ctx, asked, CFG)
    with caplog.at_level(logging.WARNING, logger="script_engine.fallback"):
        h("ANSWERED: no\nPROBE: what holds you back?")
        h("ANSWERED: yes\nACK: none")
        h("vague")
    msgs = [(r.name, r.getMessage()) for r in caplog.records]
    assert ("script_engine.fallback", "listen: probe 'what holds you back?' broke ['same_words']") in msgs
    assert ("script_engine.fallback", "listen: ack '' broke ['missing']") in msgs
    assert any("off-format" in m for _, m in msgs)


# checks
def test_checks_boundaries():
    assert clip("abc", 3) == "abc" and clip("abcdef", 3) == "abc..."
    assert "length" not in check("one two three?", ctx(max_words=3))
    assert "banned_phrase" not in check("Is your butler there?", ctx())


# engine
def test_asked_line_plain_is_empty_for_other_words():
    assert asked_line(CAT, ScriptState(step="09", asks=1, asked="Why?")) == ("Why?", "")
    assert asked_line(CAT, ScriptState(step="01", asks=1)) == (CAT.steps["01"].probes[0], "")


def test_an_objection_enters_its_branch_until_the_limit_then_books_the_follow_up():
    m1 = object_to(MINI, ScriptState(step="b", parked=("money",)), "money", entries=1)
    assert (m1.say, m1.state.raised, m1.state.parked) == ("Could you fund it?", ("money",), ())
    m2 = object_to(MINI, m1.state, "money", entries=1)
    assert m2.state.step == MINI.follow_up and m2.state.raised == ("money", "money")


# speech
def test_chunks_boundaries():
    assert speech.chunks("ab cd", 5) == ["ab cd"]
    assert speech.chunks("ab cd", 4) == ["ab", "cd"]
    assert speech.chunks("xxxxxx ab", 4) == ["xxxx", "xx", "ab"]
    assert speech.chunks("a bbbbbbbb", 5) == ["a", "bbbbb", "bbb"]
    assert speech.chunks("Hello there. Hi. Yo.", 12) == ["Hello there.", "Hi. Yo."]
    assert speech.chunks("Hi. Yo.", 7) == ["Hi. Yo."]


def _fake(monkeypatch, read):
    sent = []

    class Speech:
        def create(self, **kw):
            sent.append(kw["input"])
            return type("R", (), {"read": lambda self: read(kw["input"])})()

    class FakeGroq:
        def __init__(self, api_key):
            sent.append(("key", api_key))
            self.audio = type("A", (), {"speech": Speech()})()

    monkeypatch.setattr(speech, "Groq", FakeGroq)
    return sent


def test_one_piece_comes_back_as_sent(monkeypatch):
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k1", "k2"])
    sent = _fake(monkeypatch, lambda text: b"raw:" + text.encode())
    assert speech.speak("hi") == b"raw:hi"
    assert sent[0] == ("key", "k1")


def test_style_counts_toward_the_limit(monkeypatch):
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k"])
    monkeypatch.setitem(speech.SPEECH, "max_chars", 20)
    monkeypatch.setitem(speech.SPEECH, "style", "[s]")
    sent = _fake(monkeypatch, lambda text: b"x")
    speech.speak("ab c d e f g h i j")
    assert sent[1] == "[s] ab c d e f g h i"
    monkeypatch.setitem(speech.SPEECH, "style", "")
    sent = _fake(monkeypatch, lambda text: b"x")
    speech.speak("ab c d e f g h i j k l m")
    assert sent[1] == "ab c d e f g h i j k"


def test_empty_text_or_no_key_never_calls_the_engine(monkeypatch):
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k"])
    sent = _fake(monkeypatch, lambda text: b"x")
    assert speech.speak("   ") is None and sent == []
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: [])
    assert speech.speak("hi") is None and sent == []


def test_join_wav_keeps_the_first_format():
    def tone(rate):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            w.writeframes(b"\x01\x00" * 4)
        return buf.getvalue()
    with wave.open(io.BytesIO(speech.join_wav([tone(8000), tone(16000)]))) as w:
        assert w.getframerate() == 8000 and w.getnframes() == 8


def test_more():
    from core.script_engine.engine import ask_again
    st = ScriptState(step="00")
    for _ in range(3):
        mv = ask_again(CAT, st)
        st = mv.state
    assert mv.say == CAT.steps["00"].say and st.asks == 3
    assert "banned_phrase" not in check("Is that a rebut?", ctx())


def test_more_listen_log(caplog):
    with caplog.at_level(logging.WARNING):
        hear(lambda p, n: "ANSWERED: no\nPROBE: none", "p", 90, ctx(questions=0), ctx(), "q", CFG)
    assert "listen: probe '' broke ['missing']" in caplog.text


def test_more_speech(monkeypatch):
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k"])
    monkeypatch.setitem(speech.SPEECH, "max_chars", 20)
    monkeypatch.setitem(speech.SPEECH, "style", "[s]")
    sent = _fake(monkeypatch, lambda text: b"x")
    speech.speak("abc d e f g h i j k")
    assert sent[1] == "[s] abc d e f g h i"
    monkeypatch.setitem(speech.SPEECH, "style", "")
    sent = _fake(monkeypatch, lambda text: b"x")
    speech.speak("abc d e f g h i j k l m")
    assert sent[1] == "abc d e f g h i j k"
