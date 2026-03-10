"""Google Gemini implementation of BaseLLMProvider."""
from __future__ import annotations

import json

import structlog
from google import genai

from src.email_ingestion.types import ExtractedSubscription, SubscriptionSignal
from src.llm.base import BaseLLMProvider
from src.llm.openai_provider import _parse_response
from src.llm.prompts import SYSTEM_PROMPT, build_extraction_prompt

logger = structlog.get_logger()


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract_subscriptions(
        self,
        signals: list[SubscriptionSignal],
    ) -> list[ExtractedSubscription]:
        if not signals:
            return []

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=build_extraction_prompt(signals),
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw = json.loads(response.text or "{}")
            return _parse_response(raw)
        except Exception:
            logger.exception("llm.gemini.extraction_failed")
            return []
