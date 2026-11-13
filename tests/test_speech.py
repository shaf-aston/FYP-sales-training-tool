"""Replies read aloud: the server's voice when it has one, else 204 so the browser reads it."""

import pytest

import backend.routes.speech as route
from core.infra.providers import speech


def test_audio_comes_back_when_the_engine_speaks(client, monkeypatch):
    monkeypatch.setattr(route, "speak", lambda text, **kw: b"RIFF" + text.encode())
    res = client.post("/api/speech", json={"text": "hi"})
    assert res.status_code == 200 and res.data == b"RIFFhi" and res.mimetype.startswith("audio/")


def test_no_audio_means_the_browser_reads_it(client, monkeypatch):
    monkeypatch.setattr(route, "speak", lambda text, **kw: None)
    assert client.post("/api/speech", json={"text": "hi"}).status_code == 204


def test_long_text_goes_in_sentence_pieces_under_the_limit():
    from core.infra.providers.speech import chunks
    text = "Twenty four months. Damn. " * 12 + "x" * 250
    pieces = chunks(text, 200)
    assert all(len(p) <= 200 for p in pieces) and " ".join(pieces) == text.strip().replace("x" * 250, "x" * 200 + " " + "x" * 50)
    assert pieces[0].startswith("Twenty four months. Damn.") and len(pieces[0]) > 150  # sentences joined while they fit
    assert chunks("hi", 200) == ["hi"]


def test_pieces_come_back_as_one_wav(monkeypatch):
    import io
    import wave

    from core.infra.providers import speech

    def tone(n):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            w.writeframes(b"\x01\x00" * n)
        return buf.getvalue()

    class Audio:
        def __init__(self, text):
            self.text = text

        def read(self):
            return tone(len(self.text))

    sent = []

    class Speech:
        def create(self, **kw):
            sent.append(kw["input"])
            return Audio(kw["input"])

    class FakeGroq:
        def __init__(self, api_key):
            self.audio = type("A", (), {"speech": Speech()})()

    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k"])
    monkeypatch.setattr(speech, "Groq", FakeGroq)
    monkeypatch.setitem(speech.SPEECH, "style", "[cheerful]")
    text = "One sentence. " * 20
    out = speech.speak(text)
    with wave.open(io.BytesIO(out)) as w:
        assert w.getnframes() == sum(len(s) for s in sent)
    assert len(sent) > 1 and all(s.startswith("[cheerful] ") and len(s) <= 200 for s in sent)


def test_a_failing_piece_means_the_browser_reads_it(monkeypatch):
    from core.infra.providers import speech
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k"])
    monkeypatch.setattr(speech, "Groq", lambda api_key: (_ for _ in ()).throw(RuntimeError("terms not accepted")))
    assert speech.speak("hi") is None


def test_the_route_passes_who_is_speaking(client, monkeypatch):
    got = {}
    monkeypatch.setattr(route, "speak", lambda text, **kw: got.update(kw, text=text) or b"RIFF")
    client.post("/api/speech", json={"text": "Okay.", "speaker": "buyer", "persona": "Marcus", "speed": "fast"})
    assert got == {"text": "Okay.", "speaker": "buyer", "persona": "Marcus", "hint": "", "speed": 1.0}


def test_a_buyer_sounds_like_their_persona_and_always_the_same():
    cfg = speech.SPEECH["kokoro"]
    assert speech.pick_voice("buyer", "Marcus") in cfg["male"]          # "reflects his new role"
    assert speech.pick_voice("buyer", "Nobody", "She runs a bakery with her sister.") in cfg["female"]
    assert speech.pick_voice("buyer", "Alex") == speech.pick_voice("buyer", "Alex")
    assert speech.pick_voice("seller") == cfg["seller"]


def test_a_line_said_once_comes_back_from_the_cache(monkeypatch):
    calls = []
    monkeypatch.setitem(speech.ENGINES, "groq", lambda text, voice, speed: calls.append(text) or b"RIFFaudio")
    assert speech.speak("That's more than I was expecting.") == b"RIFFaudio"
    assert speech.speak("That's  more than I was expecting. ") == b"RIFFaudio"   # same words, same audio
    assert calls == ["That's more than I was expecting."]


def test_engines_are_tried_in_order_and_a_failure_falls_through(monkeypatch):
    monkeypatch.setitem(speech.SPEECH, "engines", ["kokoro", "groq"])
    monkeypatch.setitem(speech.ENGINES, "kokoro", lambda *a: (_ for _ in ()).throw(RuntimeError("no model files")))
    monkeypatch.setitem(speech.ENGINES, "groq", lambda *a: b"RIFFgroq")
    assert speech.speak("Hello.") == b"RIFFgroq"
    monkeypatch.setitem(speech.ENGINES, "groq", lambda *a: None)
    assert speech.speak("Hello again.") is None   # no engine: the browser reads it
    assert speech.speak("   ") is None


# --- dictation: what the learner says, as text ---

def _wav_bytes(seconds=1.0, loud=True):
    import io
    import math
    import wave
    rate = 16000
    frames = b"".join(int((8000 if loud else 0) * math.sin(i / 8)).to_bytes(2, "little", signed=True)
                      for i in range(int(rate * seconds)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def test_dictation_route_returns_the_text(client, monkeypatch):
    monkeypatch.setattr(route, "dictate", lambda audio: "What made you take this call?")
    res = client.post("/api/dictate", data={"audio": (__import__("io").BytesIO(b"webm"), "turn.webm")})
    assert res.status_code == 200 and res.get_json() == {"success": True, "text": "What made you take this call?"}


def test_nothing_heard_is_an_empty_turn_not_an_error(client, monkeypatch):
    from core.infra.providers.dictation import NoSpeech

    def silent(audio):
        raise NoSpeech("silence")
    monkeypatch.setattr(route, "dictate", silent)
    res = client.post("/api/dictate", data=b"webm")
    assert res.status_code == 200 and res.get_json()["text"] == ""


def test_dictation_refuses_no_audio_and_a_clip_too_long(client, monkeypatch):
    assert client.post("/api/dictate", data=b"").status_code == 400
    monkeypatch.setitem(route.DICTATION, "max_bytes", 10)
    assert client.post("/api/dictate", data=b"x" * 11).status_code == 413


def test_silence_and_junk_never_reach_an_engine(monkeypatch):
    from core.infra.providers import dictation
    called = []
    monkeypatch.setitem(dictation.ENGINES, "parakeet", lambda s: called.append(1) or "hi")
    with pytest.raises(dictation.NoSpeech):
        dictation.dictate(_wav_bytes(loud=False))
    with pytest.raises(dictation.NoSpeech):
        dictation.dictate(b"not audio at all")
    assert called == []


def test_dictation_engines_in_order_and_a_failure_falls_through(monkeypatch):
    from core.infra.providers import dictation
    monkeypatch.setitem(dictation.DICTATION, "engines", ["parakeet", "groq"])
    monkeypatch.setitem(dictation.ENGINES, "parakeet", lambda s: (_ for _ in ()).throw(RuntimeError("no model")))
    monkeypatch.setitem(dictation.ENGINES, "groq", lambda s: "Hello there.")
    assert dictation.dictate(_wav_bytes()) == "Hello there."
    monkeypatch.setitem(dictation.ENGINES, "groq", lambda s: " . ")   # punctuation only: nothing was said
    with pytest.raises(dictation.NoSpeech):
        dictation.dictate(_wav_bytes())


# --- lines made ahead of time must be the very ones the web asks for ---

def test_a_message_is_split_as_the_web_splits_it():
    """web/src/lib/tone.ts speakable + voice/speech/tts.ts sentences, mirrored: a cached line is only found if the
    split agrees."""
    assert speech.spoken_sentences("(slow, deliberate) Where are you **now**... that you _don't_ want?") == [
        "Where are you now...", "that you don't want?"]
    assert speech.spoken_sentences("That wears you down.¶And what would that change?") == [
        "That wears you down.", "And what would that change?"]
    assert speech.spoken_sentences("Honestly? It's ==two days== a month") == ["Honestly?", "It's two days a month."]
    assert speech.spoken_sentences("Ok. Fine") == ["Ok. Fine."]   # a scrap under 4 characters joins the next


def test_a_line_made_ahead_plays_from_the_cache(monkeypatch):
    made = []
    monkeypatch.setitem(speech.ENGINES, "kokoro", lambda text, voice, speed: made.append((text, voice)) or b"RIFFk")
    assert speech.speak("Honestly?", voice="af_heart", engines=["kokoro"]) == b"RIFFk"
    assert speech.is_cached("Honestly?", "af_heart") and not speech.is_cached("Honestly?", "am_michael")
    assert made == [("Honestly?", "af_heart")]


def test_the_prewarm_covers_the_bank_the_objections_and_the_script():
    from scripts.speech_prewarm import buyer_lines, seller_lines
    buyer = set().union(*buyer_lines().values())
    assert "That's more than I was expecting, to be honest." in buyer      # a bank line, said as the web asks
    assert "Glad to hear it." in seller_lines()                            # buy mode's common sense
    assert "So, back to you." in seller_lines()                            # engine.yaml back_to_question (missed live)
    assert all("{" not in s for s in buyer | seller_lines())                # no unfilled blanks
