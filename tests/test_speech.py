"""Replies read aloud: the server's voice when it has one, else 204 so the browser reads it."""

import backend.routes.speech as route


def test_audio_comes_back_when_the_engine_speaks(client, monkeypatch):
    monkeypatch.setattr(route, "speak", lambda text: b"RIFF" + text.encode())
    res = client.post("/api/speech", json={"text": "hi"})
    assert res.status_code == 200 and res.data == b"RIFFhi" and res.mimetype.startswith("audio/")


def test_no_audio_means_the_browser_reads_it(client, monkeypatch):
    monkeypatch.setattr(route, "speak", lambda text: None)
    assert client.post("/api/speech", json={"text": "hi"}).status_code == 204


def test_text_too_long_for_the_engine_is_never_sent(monkeypatch):
    from core.providers import speech
    monkeypatch.setattr(speech, "get_groq_api_keys", lambda: ["k"])
    assert speech.speak("a" * (speech.SPEECH["max_chars"] + 1)) is None
