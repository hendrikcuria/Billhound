"""Anthropic (Claude) implementation of BaseLLMProvider."""
from __future__ import annotations

import json

import structlog
from anthropic import AsyncAnthropic

from src.email_ingestion.types import ExtractedSubscription, SubscriptionSignal
from src.llm.base import BaseLLMProvider
from src.llm.openai_provider import _parse_response
from src.llm.prompts import SYSTEM_PROMPT, build_extraction_prompt

logger = structlog.get_logger()


class AnthropicProvider(BaseLLMProvider):
    def __init__(
        self, api_key: str, model: str = "claude-sonnet-4-20250514"
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def extract_subscriptions(
        self,
        signals: list[SubscriptionSignal],
    ) -> list[ExtractedSubscription]:
        if not signals:
            return []

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": build_extraction_prompt(signals)},
                ],
            )
            text = response.content[0].text
            raw = json.loads(text)
            return _parse_response(raw)
        except Exception:
            logger.exception("llm.anthropic.extraction_failed")
            return []
