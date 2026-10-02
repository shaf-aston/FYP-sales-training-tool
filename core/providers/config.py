"""Environment-driven provider configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DEFAULT_LLM_PROVIDER_ORDER = ["groq", "sambanova", "dummy", "probe"]
DEFAULT_LLM_FALLBACK_ORDER = DEFAULT_LLM_PROVIDER_ORDER[:]

# Groq retires models without notice and the old default (llama-3.3-70b-versatile)
# now 404s, which silently emptied every reply. Check `client.models.list()` against
# the live key when replies go blank, and override with GROQ_LLM_MODEL.
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_SAMBANOVA_MODEL = "Meta-Llama-3.3-70B-Instruct"

DEFAULT_SAMBANOVA_BASE_URL = "https://api.sambanova.ai/v1"


def _clean_env_value(value: str | None) -> str | None:
    """Strip comments and whitespace from an env var value."""
    if not value:
        return None
    cleaned = value.split("#")[0].strip()
    return cleaned or None


def _split_env_list(raw_value: str | None, fallback: list[str]) -> list[str]:
    """Parse a comma-separated provider list and fall back when empty."""
    if not raw_value:
        return fallback[:]
    values = [item.strip().lower() for item in raw_value.split(",")]
    cleaned = [item for item in values if item]
    return cleaned or fallback[:]


def get_llm_provider_order() -> list[str]:
    """Return the configured LLM provider preference order."""
    return _split_env_list(
        os.environ.get("LLM_PROVIDER_ORDER"),
        DEFAULT_LLM_PROVIDER_ORDER,
    )


def get_llm_fallback_order() -> list[str]:
    """Return the retry order for LLM fallback.

    Falls back to the primary provider order from `.env` so the retry chain
    stays aligned with the configured runtime providers unless an explicit
    override is provided.
    """

    raw_fallback = os.environ.get("LLM_PROVIDER_FALLBACK_ORDER")
    if raw_fallback:
        return _split_env_list(raw_fallback, get_llm_provider_order())
    return get_llm_provider_order()


def get_groq_llm_model() -> str:
    """Return the preferred Groq chat model, honoring env overrides."""
    return (
        _clean_env_value(os.environ.get("GROQ_LLM_MODEL"))
        or _clean_env_value(os.environ.get("GROQ_MODEL"))
        or DEFAULT_GROQ_MODEL
    )


def get_groq_api_keys() -> list[str]:
    """Return Groq keys for LLM usage.

    `SAFE_GROQ_API_KEY` is treated as the preferred chat/LLM credential.
    """

    keys = [
        os.environ.get("SAFE_GROQ_API_KEY"),
        os.environ.get("ALTERNATIVE_GROQ_API_KEY"),
        os.environ.get("GROQ_API_KEY"),
    ]
    deduped = []
    seen = set()
    for key in keys:
        if not key:
            continue
        cleaned = key.split("#")[0].strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def get_sambanova_api_key() -> str | None:
    """Return the SambaNova API key if configured."""
    return _clean_env_value(os.environ.get("SAMBANOVA_API_KEY"))


def get_sambanova_model() -> str:
    """Return the SambaNova chat model, honoring env overrides."""
    return os.environ.get("SAMBANOVA_MODEL") or DEFAULT_SAMBANOVA_MODEL


def get_sambanova_base_url() -> str:
    """Return the SambaNova API base URL, honoring env overrides."""
    return os.environ.get("SAMBANOVA_BASE_URL") or DEFAULT_SAMBANOVA_BASE_URL
