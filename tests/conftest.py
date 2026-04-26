"""Pytest configuration and fixtures for test suite."""
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "smoke: optional live integration tests (run with RUN_SMOKE_TESTS=1)"
    )


def _is_audio_provider_fallback_test(item) -> bool:
    return str(item.location[0]).endswith(
        (
            "test_audio_provider_fallbacks.py",
            "test_frontend_speech_contract.py",
        )
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if not _is_audio_provider_fallback_test(item):
        return

    item._randomly_reset_seed_original = getattr(
        item.config.option,
        "randomly_reset_seed",
        True,
    )
    item.config.option.randomly_reset_seed = False


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    original = getattr(item, "_randomly_reset_seed_original", None)
    if original is None:
        return

    item.config.option.randomly_reset_seed = original
    delattr(item, "_randomly_reset_seed_original")
