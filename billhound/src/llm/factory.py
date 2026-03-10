"""Factory function to create the correct LLM provider based on settings."""
from __future__ import annotations

from src.config.settings import Settings
from src.llm.base import BaseLLMProvider


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    api_key = settings.llm_api_key.get_secret_value()

    if settings.llm_provider == "openai":
        from src.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key, model=settings.llm_model)
    elif settings.llm_provider == "anthropic":
        from src.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=settings.llm_model)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
