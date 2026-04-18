"""Integration smoke test using the DummyProvider to exercise end-to-end chat wiring."""

from chatbot.chatbot import SalesChatbot


def test_dummy_provider_chat_smoke():
    bot = SalesChatbot(
        provider_type="dummy", model=None, product_type=None, session_id="integ_test"
    )
    resp = bot.chat("Hello there — quick question about pricing")

    assert resp is not None
    assert isinstance(resp.content, str) and resp.content
    assert resp.provider == "dummy"
    assert resp.model == "dummy-model"
