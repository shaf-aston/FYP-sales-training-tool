"""_build_response should produce a consistent ChatResponse for all code paths."""

from chatbot.chatbot import SalesChatbot, ChatResponse


def test_build_response_populates_fields_from_provider_state():
    bot = SalesChatbot(product_type="cars")
    bot._provider_name = "testing"
    bot._model_name = "test-model"

    resp = bot._build_response("hello world", 42.5, "hi")

    assert isinstance(resp, ChatResponse)
    assert resp.content == "hello world"
    assert resp.latency_ms == 42.5
    assert resp.provider == "testing"
    assert resp.model == "test-model"
    assert resp.input_len == 2
    assert resp.output_len == 11


def test_build_response_accepts_none_latency():
    bot = SalesChatbot(product_type="cars")
    resp = bot._build_response("ok", None, "hi")
    assert resp.latency_ms is None


def test_build_response_reflects_provider_swap():
    bot = SalesChatbot(product_type="cars")
    bot._provider_name = "groq"
    r1 = bot._build_response("one", 10.0, "x")
    bot._provider_name = "sambanova"
    bot._model_name = "swapped-model"
    r2 = bot._build_response("two", 20.0, "y")

    assert r1.provider == "groq"
    assert r2.provider == "sambanova"
    assert r2.model == "swapped-model"
