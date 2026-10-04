"""Tests for loader hardening and config isolation."""

import pytest

import core.loader as loader


def test_load_yaml_returns_independent_copies():
    first = loader.load_yaml("signals.yaml")
    first["commitment"].append("temporary-marker")

    second = loader.load_yaml("signals.yaml")

    assert "temporary-marker" not in second["commitment"]


def test_load_signals_rejects_unknown_signal_priority(monkeypatch):
    loader.load_signals.cache_clear()
    original_load_yaml = loader.load_yaml

    def fake_load_yaml(filename):
        if filename == "signals.yaml":
            real = original_load_yaml(filename)
            real["signal_priority"] = ["high_intent", "missing_category"]
            return real
        return original_load_yaml(filename)

    monkeypatch.setattr(loader, "load_yaml", fake_load_yaml)

    with pytest.raises(ValueError, match="signal_priority references unknown keys"):
        loader.load_signals()

    loader.load_signals.cache_clear()


def test_load_signals_fails_loud_on_missing_key(monkeypatch):
    """A broken signals.yaml raises instead of being papered over."""
    loader.load_signals.cache_clear()
    original_load_yaml = loader.load_yaml

    def fake_load_yaml(filename):
        real = original_load_yaml(filename)
        if filename == "signals.yaml":
            del real["commitment"]
        return real

    monkeypatch.setattr(loader, "load_yaml", fake_load_yaml)

    with pytest.raises(ValueError, match="commitment"):
        loader.load_signals()

    loader.load_signals.cache_clear()
