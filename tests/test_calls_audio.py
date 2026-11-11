"""A call recording -> a labelled transcript (core/calls/audio.py, /api/calls/transcribe), with the speech engine
and the AI replaced by fakes: the same input always gives the same transcript."""
import io
import re

import pytest

from core.calls.audio import as_transcript, label_speakers
from core.calls.reader import load_calls_config, read_call
from core.infra.constants import TRANSCRIPTION
from core.infra.providers.transcribe import Segment, TranscriptionUnavailable

PROMPT = load_calls_config()["speaker_prompt"]
SEGMENTS = [
    Segment(0.0, "Hi Dan, thanks for joining. What made you book the call?"),
    Segment(4.2, "I run a small agency and I'm stuck doing all the sales myself."),
    Segment(9.0, "How long has that been going on?"),
    Segment(11.5, "About a year."),
    Segment(13.0, "It's getting worse."),
    Segment(15.0, "What would good look like for you?"),
    Segment(18.0, "That's more than I budgeted for, to be honest."),
]
TRUTH = ["A", "B", "A", "B", "B", "A", "B"]


def oracle(prompt: str) -> str:
    """A fake AI that labels the segments it is shown correctly."""
    shown = re.findall(r"^(\d+)\. (?![AB]:)", prompt.split("Label each of these")[1], re.M)
    return "\n".join(f"{n}. {TRUTH[int(n) - 1]}" for n in shown)


def test_labels_come_back_per_segment_and_join_into_turns():
    labels, sure = label_speakers(SEGMENTS, oracle, PROMPT)
    assert labels == TRUTH and sure
    text = as_transcript(SEGMENTS, labels)
    assert text.splitlines()[3] == "[0:11] Speaker B: About a year. It's getting worse."
    reading = read_call(text)                                   # the reader takes it like any transcript
    assert reading.format == "speaker_lines" and reading.roles.rep == "Speaker A"
    assert reading.profile.name == "Prospect" and reading.profile.objections[0]["type"] == "price"


def test_batches_repeat_the_last_labels_for_continuity(monkeypatch):
    monkeypatch.setitem(TRANSCRIPTION, "label_batch", 3)
    monkeypatch.setitem(TRANSCRIPTION, "label_context", 2)
    prompts = []

    def recording(prompt):
        prompts.append(prompt)
        return oracle(prompt)

    assert label_speakers(SEGMENTS, recording, PROMPT)[0] == TRUTH
    assert len(prompts) == 3
    assert "2. B: I run a small agency" in prompts[1] and "3. A: How long" in prompts[1]   # context from batch 1


def test_a_missing_or_garbled_label_keeps_the_speaker_going():
    labels, sure = label_speakers(SEGMENTS, lambda prompt: "1. A\n2. B\nnonsense\n4: b\n", PROMPT)
    assert labels == ["A", "B", "B", "B", "B", "B", "B"] and not sure   # 3 of 7 readable, even after asking again


@pytest.mark.parametrize("reply", ["1. Speaker A\n2. Speaker B", "**1.** A\n**2.** B", "1 -> A\n2 -> B", "1=A\n2=B",
                                   "- 1: A\n- 2: B", "1) speaker a\n2) speaker b"])
def test_label_reply_variants_are_read(reply):
    labels, sure = label_speakers(SEGMENTS[:2], lambda prompt: reply, PROMPT)
    assert labels == ["A", "B"] and sure


def test_long_recordings_get_hour_clocks():
    assert as_transcript([Segment(3725.0, "Still here?")], ["A"]) == "[1:02:05] Speaker A: Still here?"


# --- the route ---

@pytest.fixture
def fakes(monkeypatch):
    monkeypatch.setattr("backend.routes.calls.transcribe", lambda audio, name: SEGMENTS)
    monkeypatch.setattr("backend.routes.calls.complete", lambda router, messages, **kw: oracle(messages[0]["content"]))
    monkeypatch.setattr("backend.routes.calls.ProviderRouter", lambda: None)


def upload(client, data=b"ID3fake-mp3", name="call.mp3"):
    return client.post("/api/calls/transcribe", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")


def test_a_recording_becomes_a_transcript_to_check(client, fakes):
    body = upload(client).get_json()
    assert body["filename"] == "call.txt"
    assert body["text"].startswith("[0:00] Speaker A: Hi Dan") and body["labels_sure"] is True
    assert client.post("/api/calls/read", json={"text": body["text"]}).status_code == 200


def test_a_recording_bigger_than_a_transcript_request_is_accepted(client, fakes):
    assert upload(client, b"x" * 3_000_000).status_code == 200    # the global cap is 1 MB; this route takes more


@pytest.mark.parametrize("data, name, code, status", [
    (None, None, "AUDIO_REQUIRED", 400),
    (b"x", "notes.txt", "AUDIO_FORMAT", 400),
])
def test_bad_uploads_say_why(client, fakes, data, name, code, status):
    response = upload(client, data, name) if data else client.post("/api/calls/transcribe", data={}, content_type="multipart/form-data")
    assert response.status_code == status and response.get_json()["code"] == code


def test_too_big_says_export_the_transcript(client, fakes, monkeypatch):
    monkeypatch.setitem(TRANSCRIPTION, "max_bytes", 10)
    response = upload(client, b"x" * 20)
    assert response.status_code == 413 and "transcript" in response.get_json()["error"]


def test_no_engine_points_to_transcripts(client, monkeypatch):
    def down(audio, name):
        raise TranscriptionUnavailable("no key")

    monkeypatch.setattr("backend.routes.calls.transcribe", down)
    response = upload(client)
    assert response.status_code == 503 and response.get_json()["code"] == "AUDIO_UNAVAILABLE"


def test_silence_says_so(client, fakes, monkeypatch):
    monkeypatch.setattr("backend.routes.calls.transcribe", lambda audio, name: [])
    assert upload(client).get_json()["code"] == "AUDIO_NO_SPEECH"


def test_the_engine_reply_becomes_timed_segments(monkeypatch):
    from core.infra.providers import transcribe as engine

    class FakeGroq:
        def __init__(self, **kw):
            self.audio = self

        @property
        def transcriptions(self):
            return self

        def create(self, **kw):
            assert kw["response_format"] == "verbose_json" and kw["model"] == TRANSCRIPTION["model"]
            return type("R", (), {"segments": [{"start": 1.5, "text": " Hello there. "}, {"start": 3, "text": "  "}]})()

    monkeypatch.setattr(engine, "Groq", FakeGroq)
    monkeypatch.setattr(engine, "get_groq_api_keys", lambda: ["k"])
    assert engine.transcribe(b"x", "a.mp3") == [Segment(1.5, "Hello there.")]
    monkeypatch.setattr(engine, "get_groq_api_keys", lambda: [])
    with pytest.raises(TranscriptionUnavailable):
        engine.transcribe(b"x", "a.mp3")
