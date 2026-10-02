"""Pytest configuration and fixtures for test suite."""
import sys
from pathlib import Path

import pytest

from core.providers.base import BaseLLMProvider, LLMResponse
from core.providers.factory import LLM_PROVIDER_TYPES


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyProvider(BaseLLMProvider):
    """Offline provider with a fixed reply. Registered for tests only, never in production."""

    provider_name = "dummy"

    def __init__(self, model=None):
        self.model = model or "dummy-fixed-response"

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None):
        return LLMResponse(content="Dummy provider response.")

    def is_available(self):
        return True

    def get_model_name(self):
        return self.model


LLM_PROVIDER_TYPES["dummy"] = DummyProvider


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "smoke: optional live integration tests (run with RUN_SMOKE_TESTS=1)"
    )
    # Keep pytest-randomly out of the way in this environment.
    if hasattr(config.option, "randomly_reset_seed"):
        config.option.randomly_reset_seed = False


@pytest.fixture(autouse=True)
def _no_session_leak_between_tests():
    """Sessions created through the real app outlive the test that made them.

    The managers are process-wide singletons with a session cap, so without this
    the suite slowly fills them and a much later, unrelated test fails when the
    cap is hit. Clearing after each test keeps that failure impossible rather
    than merely unlikely.
    """
    yield
    from backend import app as backend_app

    for manager in (backend_app.prospect_session_manager, backend_app.session_manager):
        with manager._lock:
            manager._sessions.clear()
