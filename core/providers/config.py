"""Environment-driven provider configuration helpers."""

from __future__ import annotations

from ..constants import DEFAULT_GROQ_MODEL, DEFAULT_LLM_PROVIDER_ORDER
from ..env import env_str


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
        env_str("LLM_PROVIDER_ORDER"),
        DEFAULT_LLM_PROVIDER_ORDER,
    )


def get_llm_fallback_order() -> list[str]:
    """Return the retry order for LLM fallback.

    Falls back to the primary provider order from `.env` so the retry chain
    stays aligned with the configured runtime providers unless an explicit
    override is provided.
    """

    raw_fallback = env_str("LLM_PROVIDER_FALLBACK_ORDER")
    if raw_fallback:
        return _split_env_list(raw_fallback, get_llm_provider_order())
    return get_llm_provider_order()


def get_groq_llm_model() -> str:
    """Return the preferred Groq chat model, honoring env overrides."""
    return (
        _clean_env_value(env_str("GROQ_LLM_MODEL"))
        or _clean_env_value(env_str("GROQ_MODEL"))
        or DEFAULT_GROQ_MODEL
    )


def get_groq_api_keys() -> list[str]:
    """Return Groq keys for LLM usage.

    `SAFE_GROQ_API_KEY` is treated as the preferred chat/LLM credential.
    """

    keys = [
        env_str("SAFE_GROQ_API_KEY"),
        env_str("ALTERNATIVE_GROQ_API_KEY"),
        env_str("GROQ_API_KEY"),
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
