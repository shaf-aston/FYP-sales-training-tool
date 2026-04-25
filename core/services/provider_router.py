"""Provider routing helpers (selection + fallback) to reduce coupling."""

from __future__ import annotations

from dataclasses import dataclass

from ..constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from ..providers import create_provider, create_provider_with_trace, list_fallback_providers
from ..providers.base import LLMResponse


@dataclass(frozen=True)
class ProviderChatResult:
    response: LLMResponse
    provider_name: str
    model_name: str


class ProviderRouter:
    def __init__(self, provider_type: str | None = None, model: str | None = None):
        provider, resolution = create_provider_with_trace(provider_type, model=model)
        self.provider = provider
        self.resolution = resolution
        self.provider_name = getattr(provider, "provider_name", "unknown")
        self.model_name = provider.get_model_name()

    def chat(self, llm_messages: list, *, stage=None) -> ProviderChatResult:
        resp = self.provider.chat(
            llm_messages,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
            stage=stage,
        )
        return ProviderChatResult(
            response=resp,
            provider_name=self.provider_name,
            model_name=self.model_name,
        )

    def chat_with_fallback(self, llm_messages: list, *, stage=None) -> ProviderChatResult:
        first = self.chat(llm_messages, stage=stage)
        if not first.response.error and (first.response.content or "").strip():
            return first

        for next_name in list_fallback_providers(self.provider_name):
            alt = create_provider(next_name)
            if not alt.is_available():
                continue
            resp = alt.chat(
                llm_messages,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=DEFAULT_MAX_TOKENS,
                stage=stage,
            )
            if resp.error or not (resp.content or "").strip():
                continue

            # Switch active provider after successful fallback.
            self.provider = alt
            self.provider_name = next_name
            self.model_name = alt.get_model_name()
            return ProviderChatResult(
                response=resp,
                provider_name=self.provider_name,
                model_name=self.model_name,
            )

        return first
