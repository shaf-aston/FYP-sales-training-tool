"""The one place that picks an AI provider and falls back to the next on failure."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from ..providers import create_provider, create_provider_with_trace, list_fallback_providers
from ..providers.base import LLMResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderChatResult:
    response: LLMResponse
    provider_name: str
    model_name: str

    @property
    def ok(self) -> bool:
        """True when the provider gave a real, non-empty reply."""
        return not self.response.error and bool((self.response.content or "").strip())


class ProviderRouter:
    def __init__(self, provider_type: str | None = None, model: str | None = None):
        """Resolve and store the active provider for chat requests."""
        provider, resolution = create_provider_with_trace(provider_type, model=model)
        self.resolution = resolution
        self._use(provider, getattr(provider, "provider_name", "unknown"))

    def _use(self, provider, name: str) -> None:
        self.provider = provider
        self.provider_name = name
        self.model_name = provider.get_model_name()

    def _result(self, response: LLMResponse) -> ProviderChatResult:
        return ProviderChatResult(response, self.provider_name, self.model_name)

    def chat_with_fallback(
        self,
        messages: list,
        *,
        stage=None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> ProviderChatResult:
        """Ask the active provider; on failure try each fallback in order.

        The first provider that answers becomes the active one. If none answer,
        the FIRST failure is returned, so callers can explain what went wrong.
        """
        kwargs = {"temperature": temperature, "max_tokens": max_tokens}
        if stage is not None:
            kwargs["stage"] = stage
        first = self._result(self.provider.chat(messages, **kwargs))
        if first.ok:
            return first

        logger.warning("provider error on %s: %s", self.provider_name, first.response.error)
        for next_name in list_fallback_providers(self.provider_name):
            try:
                alt = create_provider(next_name)
                if not alt.is_available():
                    continue
                resp = alt.chat(messages, **kwargs)
            except Exception as exc:
                logger.error("fallback to %s failed: %s", next_name, exc)
                continue
            if resp.error or not (resp.content or "").strip():
                logger.warning("fallback provider %s unavailable: %s", next_name, resp.error or "empty response")
                continue
            self._use(alt, next_name)
            logger.info("switched to %s after error", next_name)
            return self._result(resp)
        return first
