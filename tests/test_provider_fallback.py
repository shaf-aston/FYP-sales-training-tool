import pytest
from src.chatbot.chatbot import SalesChatbot
from src.chatbot.providers.base import LLMResponse, RATE_LIMIT
from src.chatbot.utils import Strategy

class FakeProvider:
    def __init__(self, responses, name="fake"):
        self.responses = responses
        self.call_count = 0
        self.name = name

    def chat(self, messages, *args, **kwargs):
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp

    def is_available(self):
        return True

    def get_model_name(self):
        return "fake-model"

def test_provider_fallback_on_rate_limit(monkeypatch):
    from src.chatbot.providers import factory
    
    # Mock registry
    original_registry = factory._PROVIDERS.copy()
    
    mock_responses1 = [LLMResponse(content="", model="fake1", latency_ms=10, error="rate limit!", error_code=RATE_LIMIT)]
    mock_responses2 = [LLMResponse(content="Hello from dummy", model="fake2", latency_ms=10)]
    
    class P1(FakeProvider):
        def __init__(self, *args, **kwargs): super().__init__(mock_responses1, "fake1")
            
    class P2(FakeProvider):
        def __init__(self, *args, **kwargs): super().__init__(mock_responses2, "fake2")
            
    factory._PROVIDERS["fake1"] = P1
    factory._PROVIDERS["openrouter"] = P2
    
    bot = SalesChatbot(provider_type="fake1")
    bot.flow_engine.flow_type = Strategy.CONSULTATIVE # bypass any extra logic
    
    resp = bot.chat("Test message")
    
    assert resp.content == "Hello from dummy"
    assert bot._provider_name == "openrouter"

    factory._PROVIDERS = original_registry
