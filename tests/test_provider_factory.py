import pytest

from core.providers.factory import create_provider, list_providers
from core.providers.llm import SambaNovaProvider


def test_create_provider_accepts_aliases_and_rejects_unknown_names():
    assert isinstance(create_provider(" Samba "), SambaNovaProvider)
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider("nope")


def test_list_providers_keeps_config_order_without_duplicates_or_unknowns(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "sambanova,bogus,sambanova")

    assert list_providers() == ["sambanova", "groq"]
