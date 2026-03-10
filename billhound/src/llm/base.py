"""Abstract interface for LLM-based subscription extraction."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.email_ingestion.types import ExtractedSubscription, SubscriptionSignal


class BaseLLMProvider(ABC):
    @abstractmethod
    async def extract_subscriptions(
        self,
        signals: list[SubscriptionSignal],
    ) -> list[ExtractedSubscription]:
        """Extract structured subscription data from raw signals."""
        ...
