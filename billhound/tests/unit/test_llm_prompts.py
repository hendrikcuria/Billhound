"""Tests for LLM prompt template generation."""
from __future__ import annotations

from src.email_ingestion.types import SubscriptionSignal
from src.llm.prompts import SYSTEM_PROMPT, build_extraction_prompt


class TestLLMPrompts:
    def test_system_prompt_contains_schema(self) -> None:
        assert "service_name" in SYSTEM_PROMPT
        assert "confidence_score" in SYSTEM_PROMPT
        assert "billing_cycle" in SYSTEM_PROMPT

    def test_system_prompt_mentions_json(self) -> None:
        assert "JSON" in SYSTEM_PROMPT

    def test_build_prompt_single_signal(self) -> None:
        signal = SubscriptionSignal(
            source="email_subject",
            raw_text="Your Netflix receipt - RM 54.00",
            sender="noreply@netflix.com",
            subject="Your Netflix receipt",
        )
        prompt = build_extraction_prompt([signal])
        assert "Source 1" in prompt
        assert "email_subject" in prompt
        assert "netflix.com" in prompt
        assert "RM 54.00" in prompt

    def test_build_prompt_multiple_signals(self) -> None:
        signals = [
            SubscriptionSignal(
                source="email_subject",
                raw_text="Netflix receipt",
                sender="noreply@netflix.com",
            ),
            SubscriptionSignal(
                source="pdf_statement",
                raw_text="01/03/2026 SPOTIFY RM 15.90",
                sender="statement@maybank.com",
            ),
        ]
        prompt = build_extraction_prompt(signals)
        assert "Source 1" in prompt
        assert "Source 2" in prompt
        assert "pdf_statement" in prompt

    def test_build_prompt_empty_signals(self) -> None:
        prompt = build_extraction_prompt([])
        assert prompt == ""
