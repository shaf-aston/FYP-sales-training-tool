"""Tests for loader hardening and config isolation."""

import core.loader as loader


def test_load_yaml_returns_independent_copies():
    first = loader.load_yaml("buyer_guardrails.yaml")
    first["buyer"]["commitment"].append("temporary-marker")

    second = loader.load_yaml("buyer_guardrails.yaml")

    assert "temporary-marker" not in second["buyer"]["commitment"]
