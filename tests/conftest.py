"""Shared fixtures: offline AI providers, app clients and stand-ins for a live session."""
import sys
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import quiz  # noqa: E402
from core.providers.base import BaseLLMProvider, LLMResponse  # noqa: E402
from core.providers.factory import LLM_PROVIDER_TYPES  # noqa: E402
from core.seller_bot import ChatResponse  # noqa: E402


class DummyProvider(BaseLLMProvider):
    """Offline provider with a fixed reply. Registered for tests only, never in production."""

    provider_name = "dummy"

    def __init__(self, model=None):
        self.model = model or "dummy-fixed-response"

    def chat(self, messages, temperature=0.8, max_tokens=200):
        return LLMResponse(content="Dummy provider response.")

    def is_available(self):
        return True

    def get_model_name(self):
        return self.model


LLM_PROVIDER_TYPES["dummy"] = DummyProvider


def pytest_configure(config):
    # Keep pytest-randomly out of the way in this environment.
    if hasattr(config.option, "randomly_reset_seed"):
        config.option.randomly_reset_seed = False


@pytest.fixture(autouse=True)
def _no_session_leak_between_tests():
    """Sessions created through the real app outlive the test that made them.

    The stores are process-wide singletons with a session cap, so without this
    the suite slowly fills them and a much later, unrelated test fails when the
    cap is hit. Clearing after each test keeps that failure impossible rather
    than merely unlikely.
    """
    yield
    from backend import app as backend_app

    for store in (backend_app.buyer_sessions, backend_app.seller_sessions):
        with store._lock:
            store._sessions.clear()


class BagOfWordsEmbedder:
    """Offline stand-in for the real embedder: hashed word counts, unit length."""

    DIM = 256

    def warm(self, texts):
        pass

    def embed(self, texts):
        import math
        import zlib

        out = []
        for text in texts:
            vec = [0.0] * self.DIM
            for word in text.lower().split():
                vec[zlib.crc32(word.strip(".,!?").encode()) % self.DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


@pytest.fixture
def fake_embedder():
    return BagOfWordsEmbedder()


@pytest.fixture(autouse=True)
def _offline_embedder(monkeypatch, fake_embedder):
    """Every SellerBot runs the script; tests use the offline embedder (no model download)."""
    monkeypatch.setattr("core.script_engine.seller.shared_embedder", lambda: fake_embedder)


# --- sell mode: an offline AI buyer ---


class StubBuyerProvider:
    """Offline AI buyer. Set `reply` for a fixed answer, or replace `chat` to inspect the prompt."""

    provider_name = "stub"

    def __init__(self, reply="Can you tell me a bit more about that?"):
        self.reply = reply

    def is_available(self):
        return True

    def get_model_name(self):
        return "stub-model"

    def chat(self, messages, temperature=0.7, max_tokens=150):
        return LLMResponse(content=self.reply)


@pytest.fixture
def stub_buyer(monkeypatch):
    """Every provider the app builds is this one stub, so a test can steer what the buyer says."""
    provider = StubBuyerProvider()
    monkeypatch.setattr("core.services.provider_router.create_provider", lambda *_a, **_k: provider)
    return provider


@pytest.fixture
def client(monkeypatch):
    """The real app. Buy mode may use the offline "dummy" provider, which the routes do not list."""
    from backend.app import app

    monkeypatch.setattr("backend.routes.buy.validate_provider", lambda data: ("dummy", None))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def sell_client(client, stub_buyer):
    """The real app with the offline AI buyer."""
    return client


@pytest.fixture
def played_session(sell_client):
    """A sell session with a pushy turn and a good one, so a review has something to say."""
    started = sell_client.post(
        "/api/sell/init", json={"difficulty": "medium", "product_type": "default"}
    ).get_json()
    headers = {"X-Session-ID": started["session_id"]}

    for message in (
        "You need to decide right now, today only.",
        "What made that matter so much? Tell me more about it.",
    ):
        sell_client.post("/api/sell/chat", json={"message": message}, headers=headers)
    return headers


# --- buy mode: a stand-in AI seller for the route tests ---


class FakeCall:
    def __init__(self):
        self.current_stage = "intent"
        self.strategy = "consultative"
        self.conversation_history = []


class FakeSeller:
    """Stands in for SellerBot behind the buy routes and records what they ask of it."""

    def __init__(self, provider_type=None, product_type=None, session_id=None):
        self.product_type = product_type
        self.session_id = session_id
        self.provider_name = provider_type or "probe"
        self.model_name = "probe-model"
        self.call = FakeCall()
        self.session_ended = False
        self.edits = []
        self.coach_questions = []

    def record_session_end(self):
        self.session_ended = True

    def script_opening(self):
        return "hello"

    def open_with(self, greeting):
        self.call.conversation_history.append({"role": "assistant", "content": greeting})

    def coach_notes(self):
        return {"what_happened": "ok"}

    def chat(self, message):
        reply = f"reply:{message}"
        self.call.conversation_history += [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ]
        return ChatResponse(reply, 12.34, "probe", "probe-model", len(message), len(reply))

    def edit_turn(self, message_index, new_text):
        self.edits.append(message_index)
        del self.call.conversation_history[message_index:]
        return self.chat(new_text)

    def answer_coach_question(self, question, style):
        self.coach_questions.append((question, style))
        return {"answer": f"{style}:{question}"}

    def score_stage_answer(self, answer):
        return quiz.score_stage_answer(answer, self.call.current_stage, self.call.strategy)

    def score_next_move(self, response):
        return quiz.score_next_move(response, None, self.call.current_stage, self.call.strategy)

    def score_direction(self, explanation):
        return quiz.score_direction(explanation, None, self.call.current_stage, self.call.strategy)


@pytest.fixture
def buy_app(monkeypatch):
    """A bare app with the buy and monitoring routes, real session stores, and SellerBot faked."""
    from backend.routes import buy, monitoring
    from backend.routes._utils import Sessions
    from backend.security import SessionStore

    monkeypatch.setattr(buy, "SellerBot", FakeSeller)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.extensions["sessions"] = Sessions(
        seller=SessionStore(max_sessions=10, idle_minutes=1, cleanup_interval=60, name="test sellers"),
        buyer=None,
    )
    app.register_blueprint(buy.bp)
    app.register_blueprint(monitoring.bp)
    return app


@pytest.fixture
def live_seller(buy_app):
    """(client, the live FakeSeller, its session headers)."""
    seller = FakeSeller(session_id="a" * 8)
    buy_app.extensions["sessions"].seller.set(seller.session_id, seller)
    return buy_app.test_client(), seller, {"X-Session-ID": seller.session_id}
