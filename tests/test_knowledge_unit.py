"""Focused unit tests for custom knowledge storage and sanitization."""

from pathlib import Path

import core.knowledge as knowledge


def test_save_custom_knowledge_sanitizes_and_writes_primary_file(monkeypatch):
    temp_dir = Path.cwd() / ".tmp" / "knowledge-unit"
    temp_dir.mkdir(parents=True, exist_ok=True)
    primary = temp_dir / "custom_instructions.yaml"
    if primary.exists():
        primary.unlink()

    monkeypatch.setattr(knowledge, "KNOWLEDGE_FILE", primary)

    saved = knowledge.save_custom_knowledge(
        {
            "product_name": "Acme Pro",
            "pricing": "$99/mo",
            "selling_points": [
                "Fast setup",
                "Custom support",
            ],
            "bad_field": "drop me",
        }
    )

    assert saved is True
    assert primary.exists()

    loaded = knowledge.load_custom_knowledge()
    assert loaded == {
        "product_name": "Acme Pro",
        "pricing": "$99/mo",
        "selling_points": ["Fast setup", "Custom support"],
    }

    knowledge_text = knowledge.get_custom_knowledge_text()
    # Each field is injected once, under its human label, with real line breaks.
    assert "\\n" not in knowledge_text  # literal backslash-n, not a line break
    assert "Product name: Acme Pro" in knowledge_text
    assert "Selling points:\n  - Fast setup\n  - Custom support" in knowledge_text
    assert knowledge_text.count("Acme Pro") == 1
    assert "product_name:" not in knowledge_text


def test_clear_custom_knowledge_removes_file(monkeypatch):
    temp_dir = Path.cwd() / ".tmp" / "knowledge-unit-clear"
    temp_dir.mkdir(parents=True, exist_ok=True)
    primary = temp_dir / "custom_instructions.yaml"
    primary.write_text("product_name: Acme Pro\n", encoding="utf-8")

    monkeypatch.setattr(knowledge, "KNOWLEDGE_FILE", primary)

    assert knowledge.clear_custom_knowledge() is True
    assert not primary.exists()
