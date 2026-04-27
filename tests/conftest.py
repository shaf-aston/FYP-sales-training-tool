"""Pytest configuration and fixtures for test suite."""
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "smoke: optional live integration tests (run with RUN_SMOKE_TESTS=1)"
    )
    # Keep pytest-randomly out of the way in this environment.
    if hasattr(config.option, "randomly_reset_seed"):
        config.option.randomly_reset_seed = False
