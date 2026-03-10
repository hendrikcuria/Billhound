"""OpenAI implementation of BaseLLMProvider."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

import structlog
from openai import AsyncOpenAI

from src.email_ingestion.types import ExtractedSubscription, SubscriptionSignal
from src.llm.base import BaseLLMProvider
from src.llm.prompts import SYSTEM_PROMPT, build_extraction_prompt

logger = structlog.get_logger()


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def extract_subscriptions(
        self,
        signals: list[SubscriptionSignal],
    ) -> list[ExtractedSubscription]:
        if not signals:
            return []

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_extraction_prompt(signals)},
                ],
                temperature=0.1,
            )
            raw = json.loads(response.choices[0].message.content or "{}")
            return _parse_response(raw)
        except Exception:
            logger.exception("llm.openai.extraction_failed")
            return []


def _parse_response(raw: dict) -> list[ExtractedSubscription]:
    """Parse LLM JSON into typed ExtractedSubscription objects."""
    # Handle both {"subscriptions": [...]} and raw [...]
    items = raw.get("subscriptions", raw if isinstance(raw, list) else [])
    if not isinstance(items, list):
        return []

    results: list[ExtractedSubscription] = []
    for item in items:
        try:
            results.append(
                ExtractedSubscription(
                    service_name=str(item.get("service_name", "Unknown")),
                    amount=Decimal(str(item.get("amount", 0))),
                    currency=str(item.get("currency", "MYR")),
                    billing_cycle=str(item.get("billing_cycle", "monthly")),
                    next_renewal_date=_parse_date(item.get("next_renewal_date")),
                    trial_end_date=_parse_date(item.get("trial_end_date")),
                    confidence_score=float(item.get("confidence_score", 0.0)),
                    source_email_subject=item.get("source_email_subject"),
                    cancellation_url=item.get("cancellation_url"),
                    category=item.get("category"),
                )
            )
        except (ValueError, InvalidOperation, TypeError):
            logger.warning("llm.parse_item_failed", item=item)
            continue
    return results


def _parse_date(value: str | None) -> None:
    """Parse ISO date string, return None on failure."""
    if not value:
        return None
    try:
        from datetime import date

        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None
