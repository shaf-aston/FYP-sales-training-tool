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
    assert speech.pick_voice("buyer", "Marcus") == "am_fenrir"           # buyer.yaml names it
    assert speech.pick_voice("buyer", "Nobody", "She runs a bakery with her sister.") in cfg["female"]
    assert speech.pick_voice("buyer", "Nobody", "Runs a bakery; his brother does the books.") in cfg["male"]
    assert speech.pick_voice("buyer", "Kelly Brown", "Runs a bakery.") in cfg["female"]   # no he or she: the name
    assert speech.pick_voice("buyer", "Gary", "Runs a bakery.") in cfg["male"]
    assert speech.pick_voice("buyer", "Robin") == speech.pick_voice("buyer", "Robin")   # either: the same each time
    assert speech.pick_voice("seller") == cfg["seller"]


def test_every_persona_speaks_in_a_voice_that_fits():
    """Live, 13 Nov: Nina, Maya, Fiona, Sophie and Zara spoke in a man's voice (nothing in their words said "she")."""
    from core.infra.loader import load_buyer_config, load_yaml
    cfg, names = speech.SPEECH["kokoro"], load_yaml("first_names.yaml")
    for product, group in load_buyer_config()["personas"].items():
        voices = [p["voice"] for p in group]
        assert len(set(voices)) == len(voices), product                  # one product: every buyer sounds different
        for p in group:
            pool = "female" if p["name"].lower() in names["female"] else "male" if p["name"].lower() in names["male"] else None
            assert p["voice"] in (cfg[pool] if pool else cfg["female"] + cfg["male"]), p["name"]
            hint = f"{p['background']} {p['personality']}"                # as the web sends it
            assert speech.pick_voice("buyer", p["name"], hint) == p["voice"]
    toms = [p for g in load_buyer_config()["personas"].values() for p in g if p["name"] == "Tom"]
    assert len({speech.pick_voice("buyer", "Tom", f"{t['background']} {t['personality']}") for t in toms}) == 2
    assert not set(names["female"]) & set(names["male"])


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
        "Where are you **now**...", "that you _don't_ want?"]   # the marks go to the voice, the tone note doesn't
    assert speech.spoken_sentences("That wears you down.¶And what would that change?") == [
        "That wears you down.", "And what would that change?"]
    assert speech.spoken_sentences("Honestly? It's ==two days== a month") == ["Honestly?", "It's ==two days== a month."]
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
    seller = {s for s, _ in seller_lines()}
    assert "Glad to hear it." in seller                                    # buy mode's common sense
    assert "So, back to you." in seller                                    # engine.yaml back_to_question (missed live)
    assert all("{" not in s for s in buyer | seller)                       # no unfilled blanks


def test_the_prewarm_makes_a_line_at_its_tone_notes_pace():
    from scripts.speech_prewarm import seller_lines
    lines = seller_lines()
    assert ("What is it about where you are **now**...", 0.85 * 0.9) in lines   # cat.yaml's (slow, deliberate) probe
    assert ("Glad to hear it.", 1) in lines


def test_the_tone_paces_match_the_web():
    """lib/tone.ts TONES and tone.py RATES: the pace is part of a made line's name in the cache."""
    import re
    from pathlib import Path

    from core.buy_mode.script_engine.words.tone import RATES
    web = (Path(__file__).resolve().parent.parent / "web/src/lib/tone.ts").read_text()
    block = web[web.index("const TONES"):web.index("};", web.index("const TONES"))]
    assert {w: float(r) for w, r in re.findall(r"(\w+): ([\d.]+)", block)} == {w: float(r) for w, r in RATES.items()}


def test_prices_are_said_the_way_people_say_them():
    """The voice's own reading of "$4,000" is "dollar four thousand"."""
    assert speech.readable("It's $4,000 for the year.") == "It's 4,000 dollars for the year."
    assert speech.readable("About £300 a month, £1.50 a day, €50 once.") == \
        "About 300 pounds a month, 1 pound 50 a day, 50 euros once."
    assert speech.readable("£2.5k up front, $2m budget, 4k all in") == \
        "2.5 thousand pounds up front, 2 million dollars budget, 4 thousand all in"
    assert speech.readable("We're 60 people, 10.5% up, v4k") == "We're 60 people, 10.5% up, v4k"
    assert speech._cache_path("kokoro", "x", 1, "$4,000.") == speech._cache_path("kokoro", "x", 1, "4,000 dollars.")


def test_dictation_turn_during_parakeet_load_goes_to_groq_and_loads_once(monkeypatch):
    """A turn spoken while the local model loads must not wait for it, or start a second load."""
    import threading
    from core.infra.providers import dictation

    loads, release = [], threading.Event()

    class Slow:
        def __init__(self):
            loads.append(1)
            release.wait(5)

        def hear(self, s):
            return "local"

    dictation.parakeet.cache_clear()
    monkeypatch.setattr(dictation, "_Parakeet", Slow)
    monkeypatch.setitem(dictation.DICTATION, "engines", ["parakeet", "groq"])
    monkeypatch.setitem(dictation.ENGINES, "groq", lambda s: "from groq")
    try:
        assert dictation.dictate(_wav_bytes()) == "from groq"
        assert dictation.dictate(_wav_bytes()) == "from groq"
        release.set()
        for _ in range(100):
            if dictation.parakeet.cache_info().currsize and not dictation._loading:
                break
            threading.Event().wait(0.02)
        assert dictation.dictate(_wav_bytes()) == "local"
        assert loads == [1]
    finally:
        release.set()
        dictation.parakeet.cache_clear()


# --- Gemini TTS: the human voice first, Kokoro when it has no key or is resting ---

def _gemini(monkeypatch, error=None):
    import base64
    import io as _io
    import json as _json
    import urllib.error
    from core.infra.providers import speech

    sent = []
    audio = speech._pcm_wav(b"\x00\x00" * 2400, 24000)
    ok = {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": base64.b64encode(audio).decode()}]}]}

    def urlopen(req, timeout):
        sent.append(_json.loads(req.data))
        if error:
            raise urllib.error.HTTPError(req.full_url, error, "no", {}, None)
        return _io.BytesIO(_json.dumps(ok).encode())
    monkeypatch.setattr(speech.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(speech, "env_str", lambda k: "key" if k == "GEMINI_API_KEY" else None)
    monkeypatch.setattr(speech, "_gemini_rest_until", 0.0)
    monkeypatch.setitem(speech.SPEECH, "engines", ["gemini", "groq"])
    return speech, sent


def test_gemini_speaks_first_in_a_matching_voice_and_plain_words(monkeypatch):
    speech, sent = _gemini(monkeypatch)
    audio = speech.speak("It's **really** $4,000.", speaker="seller", speed=0.8)
    assert audio[:4] == b"RIFF"
    body = sent[0]
    assert body["generation_config"]["speech_config"][0]["voice"] == speech.SPEECH["gemini"]["seller"]
    said = body["input"][0]["content"][0]
    assert "**" not in said["text"] and "dollars" in said["text"]
    assert "slower" in said["annotations"][0]["style"]


def test_a_buyer_gets_a_gemini_voice_of_the_same_kind_every_time():
    from core.infra.providers import speech
    g = speech.SPEECH["gemini"]
    assert speech.gemini_voice("af_heart") in g["female"] and speech.gemini_voice("bm_george") in g["male"]
    assert speech.gemini_voice("af_heart") == speech.gemini_voice("af_heart")


def test_gemini_refused_rests_and_the_next_engine_speaks(monkeypatch):
    speech, sent = _gemini(monkeypatch, error=429)
    monkeypatch.setattr(speech, "_groq_engine", lambda t, v, s: b"RIFFgroq")
    monkeypatch.setitem(speech.ENGINES, "groq", lambda t, v, s: b"RIFFgroq")
    assert speech.speak("Hello there.") == b"RIFFgroq"
    assert speech.speak("Another line.") == b"RIFFgroq"
    assert len(sent) == 1   # resting: not asked again on the next line


def test_no_gemini_key_means_no_call(monkeypatch):
    speech, sent = _gemini(monkeypatch)
    monkeypatch.setattr(speech, "env_str", lambda k: None)
    monkeypatch.setitem(speech.ENGINES, "groq", lambda t, v, s: b"RIFFgroq")
    assert speech.speak("Hi.") == b"RIFFgroq" and sent == []


def test_prewarm_with_gemini_is_capped_and_stops_at_the_first_refusal(monkeypatch):
    import scripts.speech_prewarm as pw
    monkeypatch.setitem(pw.SPEECH, "engines", ["gemini", "groq"])
    monkeypatch.setitem(pw.SPEECH, "gemini", {**pw.SPEECH["gemini"], "prewarm_per_run": 3})
    monkeypatch.setattr(pw, "seller_lines", lambda: [("one.", 1.0), ("two two.", 1.0), ("three 3.", 1.0), ("four 44.", 1.0)])
    monkeypatch.setattr(pw, "buyer_lines", lambda: {})
    monkeypatch.setattr(pw, "is_cached", lambda *a: False)
    asked = []
    monkeypatch.setattr(pw, "speak", lambda s, **k: asked.append((s, k["engines"])) or (b"wav" if len(asked) < 2 else None))
    pw.main()
    assert asked == [("one.", ["gemini"]), ("two two.", ["gemini"])]   # capped at 3, stopped at the refusal


def test_a_machine_picks_its_own_engines_from_its_env():
    import os
    import subprocess
    import sys
    code = "from core.infra.constants import SPEECH, DICTATION; print(SPEECH['engines'], DICTATION['engines'])"
    env = {**os.environ, "SPEECH_ENGINES": " kokoro, groq ", "DICTATION_ENGINES": "parakeet,groq"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout
    assert out.strip() == "['kokoro', 'groq'] ['parakeet', 'groq']"
