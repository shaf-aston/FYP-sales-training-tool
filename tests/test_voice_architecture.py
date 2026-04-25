"""Tests for voice system architecture and speech I/O integration."""
from io import BytesIO
from pathlib import Path

from flask import Flask

from backend.routes import voice as voice_routes
from core.providers.factory import create_provider, list_providers
from core.providers.base import SynthesisResult, TranscriptionResult
from core.providers.stt.deepgram import DeepgramSTTProvider
from core.providers.voice_provider import VoiceProvider


ROOT = Path(__file__).resolve().parent.parent


def _make_voice_app():
    app = Flask(__name__)
    app.config["TESTING"] = True

    def require_session():
        class DummyBot:
            def chat(self, message):
                class Resp:
                    content = "Acknowledged."
                    latency_ms = 10.0
                    provider = "probe"
                    model = "probe-model"

                return Resp()

            def generate_training(self, *_args, **_kwargs):
                return {"what_happened": "ok"}

        return DummyBot(), None

    def validate_message(text):
        return text, None

    def bot_state(_bot):
        return {"stage": "INTENT", "strategy": "CONSULTATIVE"}

    voice_routes._voice_provider = None
    voice_routes.init_routes(app, require_session, validate_message, bot_state)
    app.register_blueprint(voice_routes.bp)
    return app


def test_speech_js_matches_capture_contract():
    speech_js = (ROOT / "frontend" / "static" / "speech.js").read_text(
        encoding="utf-8"
    )

    assert "this.recognition.continuous = true;" in speech_js
    assert "this.recognition.interimResults = true;" in speech_js
    assert "this.recognition.onend" in speech_js
    assert "this.recognition.start();" in speech_js


def test_list_providers_respects_env_order(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "sambanova,groq,probe")

    assert list_providers()[:3] == ["sambanova", "groq", "probe"]


def test_create_provider_builds_groq_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,sambanova")
    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-key")
    provider = create_provider()

    assert provider.provider_name == "groq"


def test_voice_provider_uses_deepgram_for_stt(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    voice_provider = VoiceProvider()

    class WorkingSTT:
        provider_name = "deepgram"

        def is_available(self):
            return True

        def transcribe(self, audio_bytes, filename="audio.webm"):
            return TranscriptionResult(
                provider="deepgram",
                text="normalized transcript",
            )

    monkeypatch.setattr(voice_provider, "_build_stt_provider", lambda _name: WorkingSTT())

    result = voice_provider.transcribe(b"fake-audio", filename="sample.webm")

    assert result.text == "normalized transcript"
    assert result.provider == "deepgram"


def test_voice_provider_returns_deepgram_error_when_transcription_fails(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    voice_provider = VoiceProvider()

    class FailingSTT:
        provider_name = "deepgram"

        def is_available(self):
            return True

        def transcribe(self, audio_bytes, filename="audio.webm"):
            return TranscriptionResult(
                provider="deepgram",
                error="Deepgram request failed.",
            )

    monkeypatch.setattr(voice_provider, "_build_stt_provider", lambda _name: FailingSTT())

    result = voice_provider.transcribe(b"fake-audio", filename="sample.webm")

    assert result.error == "Deepgram request failed."


def test_voice_provider_uses_edge_for_tts(monkeypatch):
    voice_provider = VoiceProvider()

    class WorkingTTS:
        provider_name = "edge"

        def is_available(self):
            return True

        def synthesize(self, text, voice="male_us", rate=0):
            return SynthesisResult(
                provider="edge",
                voice=voice,
                audio_bytes=b"ok",
                content_type="audio/mpeg",
            )

    monkeypatch.setattr(
        voice_provider,
        "_build_tts_provider",
        lambda _provider_name: WorkingTTS(),
    )

    result = voice_provider.synthesize("hello", voice="male_us")

    assert result.audio_bytes == b"ok"
    assert result.provider == "edge"


def test_voice_provider_returns_edge_error_when_synthesis_fails(monkeypatch):
    voice_provider = VoiceProvider()

    class FailingTTS:
        provider_name = "edge"

        def is_available(self):
            return True

        def synthesize(self, text, voice="male_us", rate=0):
            return SynthesisResult(
                provider="edge",
                voice=voice,
                error="Edge TTS failed",
            )

    monkeypatch.setattr(voice_provider, "_build_tts_provider", lambda _name: FailingTTS())

    result = voice_provider.synthesize("hello", voice="male_us")

    assert result.error == "Edge TTS failed"


def test_deepgram_provider_transcribes_with_smart_format(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    DeepgramSTTProvider._rate_limit_until = 0.0
    provider = DeepgramSTTProvider()

    captured = {}

    def fake_post_bytes(url, body, headers, timeout=30):
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        return (
            b'{"results":{"channels":[{"alternatives":[{"transcript":"hello world"}]}]}}',
            {},
        )

    monkeypatch.setattr("core.providers.stt.deepgram.post_bytes", fake_post_bytes)

    result = provider.transcribe(b"audio-bytes", filename="sample.webm")

    assert result.text == "hello world"
    assert result.provider == "deepgram"
    assert "model=nova-2" in captured["url"]
    assert "smart_format=true" in captured["url"]
    assert captured["headers"]["Authorization"] == "Token test-key"
    assert captured["headers"]["Content-Type"] == "audio/webm"


def test_deepgram_provider_applies_rate_limit_cooldown(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    DeepgramSTTProvider._rate_limit_until = 0.0
    provider = DeepgramSTTProvider()

    def fake_post_bytes(*_args, **_kwargs):
        from core.providers.http import ProviderHTTPError

        raise ProviderHTTPError(429, "rate limited", "Too Many Requests")

    monkeypatch.setattr("core.providers.stt.deepgram.post_bytes", fake_post_bytes)

    result = provider.transcribe(b"audio-bytes", filename="sample.webm")

    assert result.rate_limited is True
    assert (result.error or "").startswith("Deepgram HTTP 429")
    assert provider.is_available() is False
    DeepgramSTTProvider._rate_limit_until = 0.0


def test_voice_transcribe_rejects_unsupported_audio_extension():
    app = _make_voice_app()
    client = app.test_client()

    response = client.post(
        "/api/voice/transcribe",
        data={"audio": (BytesIO(b"abc"), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"].startswith("Unsupported audio format")


def test_voice_transcribe_surfaces_fallback_metadata(monkeypatch):
    app = _make_voice_app()
    client = app.test_client()

    class DummyProvider:
        def transcribe(self, audio_bytes, filename="audio.webm"):
            return TranscriptionResult(
                provider="deepgram",
                error="Deepgram HTTP 429: rate limited.",
                rate_limited=True,
            )

    monkeypatch.setattr(voice_routes, "_voice_provider", DummyProvider())

    response = client.post(
        "/api/voice/transcribe",
        data={"audio": (BytesIO(b"abc"), "voice.webm")},
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["fallback_recommended"] is None
    assert payload["rate_limited"] is True


def test_voice_synthesize_surfaces_fallback_metadata(monkeypatch):
    app = _make_voice_app()
    client = app.test_client()

    class DummyProvider:
        def synthesize(self, text, voice="male_us", rate=0):
            return SynthesisResult(
                provider="edge",
                voice=voice,
                error="Edge TTS unavailable.",
            )

    monkeypatch.setattr(voice_routes, "_voice_provider", DummyProvider())

    response = client.post(
        "/api/voice/synthesize",
        json={"text": "Hello there", "voice": "male_us"},
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["fallback_recommended"] is None


def test_voice_chat_surfaces_tts_failure(monkeypatch):
    app = _make_voice_app()
    client = app.test_client()

    class DummyProvider:
        def transcribe(self, audio_bytes, filename="audio.webm"):
            return TranscriptionResult(
                provider="deepgram",
                text="Hello there",
                latency_ms=12.5,
            )

        def synthesize(self, text, voice="male_us", rate=0):
            return SynthesisResult(
                provider="edge",
                voice=voice,
                error="Edge TTS synthesis failed.",
                latency_ms=21.0,
            )

    monkeypatch.setattr(voice_routes, "_voice_provider", DummyProvider())

    response = client.post(
        "/api/voice/chat",
        data={"audio": (BytesIO(b"abc"), "voice.webm"), "voice": "male_us"},
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["success"] is False
    assert payload["tts_fallback_recommended"] is None
    assert payload["transcription"] == "Hello there"


def test_voice_chat_returns_audio_blob_on_success(monkeypatch):
    app = _make_voice_app()
    client = app.test_client()

    class DummyProvider:
        def transcribe(self, audio_bytes, filename="audio.webm"):
            return TranscriptionResult(
                provider="deepgram",
                text="Hello there",
                latency_ms=12.5,
            )

        def synthesize(self, text, voice="male_us", rate=0):
            return SynthesisResult(
                provider="edge",
                voice=voice,
                audio_bytes=b"ok",
                content_type="audio/mpeg",
                latency_ms=21.0,
            )

    monkeypatch.setattr(voice_routes, "_voice_provider", DummyProvider())

    response = client.post(
        "/api/voice/chat",
        data={"audio": (BytesIO(b"abc"), "voice.webm"), "voice": "male_us"},
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["audio"]
    assert payload["audio_type"] == "audio/mpeg"
    assert payload["voice"] == "male_us"
