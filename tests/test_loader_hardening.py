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
            return {"signal_priority": ["high_intent", "missing_category"]}
        return original_load_yaml(filename)

    monkeypatch.setattr(loader, "load_yaml", fake_load_yaml)

    with pytest.raises(ValueError, match="signal_priority references unknown keys"):
        loader.load_signals()

    loader.load_signals.cache_clear()
