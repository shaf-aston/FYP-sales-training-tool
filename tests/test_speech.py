"""Replies read aloud: the server's voice when it has one, else 204 so the browser reads it."""

import backend.routes.speech as route


def test_audio_comes_back_when_the_engine_speaks(client, monkeypatch):
    monkeypatch.setattr(route, "speak", lambda text: b"RIFF" + text.encode())
    res = client.post("/api/speech", json={"text": "hi"})
    assert res.status_code == 200 and res.data == b"RIFFhi" and res.mimetype.startswith("audio/")


def test_no_audio_means_the_browser_reads_it(client, monkeypatch):
    monkeypatch.setattr(route, "speak", lambda text: None)
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
