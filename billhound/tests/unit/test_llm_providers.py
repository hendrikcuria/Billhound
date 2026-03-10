"""Tests for LLM providers — mock API responses, JSON parsing."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.email_ingestion.types import SubscriptionSignal
from src.llm.gemini_provider import GeminiProvider
from src.llm.openai_provider import OpenAIProvider, _parse_response


class TestParseResponse:
    def test_valid_response(self) -> None:
        raw = {
            "subscriptions": [
                {
                    "service_name": "Netflix",
                    "amount": 54.00,
                    "currency": "MYR",
                    "billing_cycle": "monthly",
                    "confidence_score": 0.95,
                }
            ]
        }
        results = _parse_response(raw)
        assert len(results) == 1
        assert results[0].service_name == "Netflix"
        assert results[0].amount == Decimal("54.00")
        assert results[0].confidence_score == 0.95

    def test_multiple_subscriptions(self) -> None:
        raw = {
            "subscriptions": [
                {"service_name": "Netflix", "amount": 54.00, "confidence_score": 0.9},
                {"service_name": "Spotify", "amount": 15.90, "confidence_score": 0.85},
            ]
        }
        results = _parse_response(raw)
        assert len(results) == 2

    def test_empty_subscriptions(self) -> None:
        raw = {"subscriptions": []}
        results = _parse_response(raw)
        assert len(results) == 0

    def test_missing_subscriptions_key(self) -> None:
        raw = {}
        results = _parse_response(raw)
        assert len(results) == 0

    def test_date_parsing(self) -> None:
        raw = {
            "subscriptions": [
                {
                    "service_name": "Netflix",
                    "amount": 54.00,
                    "next_renewal_date": "2026-04-15",
                    "trial_end_date": None,
                    "confidence_score": 0.9,
                }
            ]
        }
        results = _parse_response(raw)
        assert results[0].next_renewal_date is not None
        assert results[0].trial_end_date is None

    def test_malformed_item_skipped(self) -> None:
        raw = {
            "subscriptions": [
                {"service_name": "Netflix", "amount": 54.00, "confidence_score": 0.9},
                {"service_name": "Bad", "amount": "not_a_number"},
            ]
        }
        results = _parse_response(raw)
        assert len(results) >= 1
        assert results[0].service_name == "Netflix"

    def test_defaults_applied(self) -> None:
        raw = {
            "subscriptions": [
                {"service_name": "SomeService", "amount": 10.00}
            ]
        }
        results = _parse_response(raw)
        assert results[0].currency == "MYR"
        assert results[0].billing_cycle == "monthly"
        assert results[0].confidence_score == 0.0


class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_extract_with_mock(self) -> None:
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "subscriptions": [
                            {
                                "service_name": "Netflix",
                                "amount": 54.00,
                                "confidence_score": 0.95,
                            }
                        ]
                    })
                )
            )
        ]

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            signals = [
                SubscriptionSignal(
                    source="email_subject",
                    raw_text="Netflix receipt RM 54.00",
                    sender="noreply@netflix.com",
                )
            ]
            results = await provider.extract_subscriptions(signals)
            assert len(results) == 1
            assert results[0].service_name == "Netflix"

    @pytest.mark.asyncio
    async def test_empty_signals(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        results = await provider.extract_subscriptions([])
        assert results == []

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self) -> None:
        provider = OpenAIProvider(api_key="test-key")

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            signals = [
                SubscriptionSignal(
                    source="email_body",
                    raw_text="test",
                    sender="test@test.com",
                )
            ]
            results = await provider.extract_subscriptions(signals)
            assert results == []


class TestGeminiProvider:
    @pytest.mark.asyncio
    async def test_extract_with_mock(self) -> None:
        provider = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "subscriptions": [
                {
                    "service_name": "Netflix",
                    "amount": 54.00,
                    "confidence_score": 0.95,
                }
            ]
        })

        with patch.object(
            provider._client.aio.models,
            "generate_content",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            signals = [
                SubscriptionSignal(
                    source="email_subject",
                    raw_text="Netflix receipt RM 54.00",
                    sender="noreply@netflix.com",
                )
            ]
            results = await provider.extract_subscriptions(signals)
            assert len(results) == 1
            assert results[0].service_name == "Netflix"

    @pytest.mark.asyncio
    async def test_empty_signals(self) -> None:
        provider = GeminiProvider(api_key="test-key")
        results = await provider.extract_subscriptions([])
        assert results == []

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self) -> None:
        provider = GeminiProvider(api_key="test-key")

        with patch.object(
            provider._client.aio.models,
            "generate_content",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            signals = [
                SubscriptionSignal(
                    source="email_body",
                    raw_text="test",
                    sender="test@test.com",
                )
            ]
            results = await provider.extract_subscriptions(signals)
            assert results == []
