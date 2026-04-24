from pathlib import Path
from typing import Any, cast

from backend.app import app
from core.chatbot import SalesChatbot
from core.providers.factory import create_provider
from core.providers.llm.groq import GroqProvider
from core.providers.base import LLMResponse
from core.providers.stt.groq import GroqSTTProvider
from core.providers.tts.groq import GroqTTSProvider
from core import session_persistence


def test_groq_provider_uses_llm_model_alias(monkeypatch):
    monkeypatch.setenv("GROQ_LLM_MODEL", "env-model")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-key")

    provider = GroqProvider()

    assert provider.get_model_name() == "env-model"


def test_safe_groq_key_is_reserved_for_llm(monkeypatch):
    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-safe-key")
    monkeypatch.delenv("ALTERNATIVE_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    llm_provider = GroqProvider()
    stt_provider = GroqSTTProvider()
    tts_provider = GroqTTSProvider()

    assert llm_provider.is_available() is True
    assert stt_provider.is_available() is False
    assert tts_provider.is_available() is False


def test_create_provider_defaults_to_groq_when_groq_is_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,sambanova,dummy,probe")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("SAFE_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("SAMBANOVA_API_KEY", raising=False)

    provider = create_provider()

    assert provider.provider_name == "groq"


def test_api_init_uses_backend_provider_order_when_provider_not_supplied(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setenv("LLM_PROVIDER_ORDER", "sambanova,groq")
    monkeypatch.delenv("SAFE_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ALTERNATIVE_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("SAMBANOVA_API_KEY", "test-sambanova-key")

    response = client.post("/api/init", json={})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True

    session_id = payload["session_id"]
    session_manager = cast(Any, app.blueprints["session"]).session_manager
    bot = session_manager.get(session_id)
    assert bot is not None
    assert bot.provider_name == "sambanova"


def test_chat_falls_back_after_non_rate_limit_provider_error(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,sambanova")

    init_response = client.post("/api/init", json={"provider": "groq"})
    init_payload = init_response.get_json()
    session_id = init_payload["session_id"]

    session_manager = cast(Any, app.blueprints["session"]).session_manager
    bot = session_manager.get(session_id)
    assert bot is not None

    monkeypatch.setattr(
        bot.provider,
        "chat",
        lambda *_args, **_kwargs: LLMResponse(error="Groq HTTP 401: invalid key", latency_ms=5.0),
    )

    class FallbackProvider:
        provider_name = "sambanova"

        def is_available(self):
            return True

        def get_model_name(self):
            return "fallback-model"

        def chat(self, *_args, **_kwargs):
            return LLMResponse(content="Fallback reply", latency_ms=7.0)

    monkeypatch.setattr("core.chatbot.create_provider", lambda name, model=None: FallbackProvider())
    monkeypatch.setattr(SalesChatbot, "generate_training", lambda *_args, **_kwargs: {})

    response = client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={"message": "Hi"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["message"] == "Fallback reply"
    assert payload["provider"] == "sambanova"


def test_chat_fallback_prefers_groq_when_active_provider_is_sambanova(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-key")
    monkeypatch.setenv("SAMBANOVA_API_KEY", "test-sambanova-key")
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "sambanova,groq")

    init_response = client.post("/api/init", json={"provider": "sambanova"})
    init_payload = init_response.get_json()
    session_id = init_payload["session_id"]

    session_manager = cast(Any, app.blueprints["session"]).session_manager
    bot = session_manager.get(session_id)
    assert bot is not None

    monkeypatch.setattr(
        bot.provider,
        "chat",
        lambda *_args, **_kwargs: LLMResponse(
            error="SambaNova HTTP 429: rate limited",
            error_code="rate_limit",
            latency_ms=5.0,
        ),
    )

    provider_calls: list[str] = []

    class GroqFallbackProvider:
        provider_name = "groq"

        def is_available(self):
            return True

        def get_model_name(self):
            return "groq-fallback-model"

        def chat(self, *_args, **_kwargs):
            return LLMResponse(content="Groq fallback reply", latency_ms=7.0)

    class SambaFallbackProvider:
        provider_name = "sambanova"

        def is_available(self):
            return True

        def get_model_name(self):
            return "samba-fallback-model"

        def chat(self, *_args, **_kwargs):
            return LLMResponse(content="Samba fallback reply", latency_ms=7.0)

    def fake_create_provider(name, model=None):
        provider_calls.append(name)
        if name == "groq":
            return GroqFallbackProvider()
        if name == "sambanova":
            return SambaFallbackProvider()
        raise AssertionError(f"Unexpected fallback provider: {name}")

    monkeypatch.setattr("core.chatbot.create_provider", fake_create_provider)
    monkeypatch.setattr(SalesChatbot, "generate_training", lambda *_args, **_kwargs: {})

    response = client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={"message": "Hi"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["message"] == "Groq fallback reply"
    assert payload["provider"] == "groq"
    assert provider_calls[0] == "groq"


def test_chat_surfaces_blocked_network_error_when_all_providers_are_denied(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-key")

    init_response = client.post("/api/init", json={"provider": "groq"})
    init_payload = init_response.get_json()
    session_id = init_payload["session_id"]

    session_manager = cast(Any, app.blueprints["session"]).session_manager
    bot = session_manager.get(session_id)
    assert bot is not None

    monkeypatch.setattr(
        bot.provider,
        "chat",
        lambda *_args, **_kwargs: LLMResponse(
            error=(
                "Groq request failed: <urlopen error [WinError 10013] "
                "An attempt was made to access a socket in a way forbidden "
                "by its access permissions>"
            ),
            latency_ms=5.0,
        ),
    )
    monkeypatch.setattr("core.chatbot.list_fallback_providers", lambda _current: [])
    monkeypatch.setattr(SalesChatbot, "generate_training", lambda *_args, **_kwargs: {})

    response = client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={"message": "Hi"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["message"].startswith("Groq is rejecting this request")
    assert payload["provider"] == "groq"


def test_chat_surfaces_groq_access_denied_error_code_1010(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setenv("SAFE_GROQ_API_KEY", "test-key")

    init_response = client.post("/api/init", json={"provider": "groq"})
    init_payload = init_response.get_json()
    session_id = init_payload["session_id"]

    session_manager = cast(Any, app.blueprints["session"]).session_manager
    bot = session_manager.get(session_id)
    assert bot is not None

    monkeypatch.setattr(
        bot.provider,
        "chat",
        lambda *_args, **_kwargs: LLMResponse(
            error="Groq HTTP 403: error code: 1010",
            error_code="access_denied",
            latency_ms=5.0,
        ),
    )
    monkeypatch.setattr("core.chatbot.list_fallback_providers", lambda _current: [])
    monkeypatch.setattr(SalesChatbot, "generate_training", lambda *_args, **_kwargs: {})

    response = client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={"message": "Hi"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["message"].startswith("Groq is rejecting this request")
    assert payload["provider"] == "groq"


def test_session_persistence_stays_inside_repo():
    repo_root = Path(__file__).resolve().parent.parent
    sessions_dir = Path(session_persistence.SESSIONS_DIR).resolve()

    assert sessions_dir == (repo_root / "sessions").resolve()
