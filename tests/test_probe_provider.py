"""Focused tests for the probe LLM provider."""

from __future__ import annotations

import json

from core.providers.factory import create_provider
from core.providers.llm.probe import ProbeProvider


def test_create_provider_builds_probe_provider():
    provider = create_provider("probe")

    assert isinstance(provider, ProbeProvider)
    assert provider.provider_name == "probe"
    assert provider.get_model_name() == "probe-json"
    assert provider.is_available() is True


def test_probe_provider_echoes_request_payload():
    provider = ProbeProvider()

    response = provider.chat(
        [{"role": "user", "content": "hello"}],
        temperature=0.2,
        max_tokens=42,
        stage="debug",
    )

    payload = json.loads(response.content)

    assert payload == {
        "message_count": 1,
        "temperature": 0.2,
        "max_tokens": 42,
        "stage": "debug",
        "messages": [{"role": "user", "content": "hello"}],
    }
