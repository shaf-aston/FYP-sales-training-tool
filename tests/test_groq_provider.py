import pytest
from chatbot.providers.groq_provider import GroqProvider

@pytest.fixture
def groq_provider():
    return GroqProvider(model="test-model")

def test_chat(groq_provider):
    response = groq_provider.chat(
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.7,
        max_tokens=50
    )
    assert response is not None

def test_is_available(groq_provider):
    assert groq_provider.is_available() is True

def test_get_model_name(groq_provider):
    assert groq_provider.get_model_name() == "test-model"