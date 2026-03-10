"""Tests for EmailParser — keyword matching, amount extraction, sender identification."""
from __future__ import annotations

from src.email_ingestion.parser import EmailParser
from src.email_ingestion.types import RawEmail


def _make_email(**overrides) -> RawEmail:
    defaults = {
        "message_id": "msg_001",
        "subject": "Test subject",
        "sender": "test@example.com",
        "body_text": "Test body",
        "received_at": "2026-03-01T10:00:00Z",
    }
    defaults.update(overrides)
    return RawEmail(**defaults)


class TestEmailParser:
    def setup_method(self) -> None:
        self.parser = EmailParser()

    def test_subscription_keyword_in_subject(self) -> None:
        email = _make_email(subject="Your Netflix subscription receipt")
        signals = self.parser.parse(email)
        assert len(signals) >= 1
        assert signals[0].source == "email_subject"

    def test_payment_keyword_in_body(self) -> None:
        email = _make_email(
            subject="Hello",
            body_text="Your monthly payment of RM 54.00 has been processed.",
        )
        signals = self.parser.parse(email)
        assert len(signals) >= 1
        assert any(s.source == "email_body" for s in signals)

    def test_amount_pattern_triggers_signal(self) -> None:
        email = _make_email(
            subject="Hello",
            body_text="Charged RM 15.90 to your card",
        )
        signals = self.parser.parse(email)
        assert len(signals) >= 1

    def test_no_match_returns_empty(self) -> None:
        email = _make_email(
            subject="Meeting tomorrow",
            body_text="Let's discuss the project updates.",
        )
        signals = self.parser.parse(email)
        assert len(signals) == 0

    def test_known_sender_creates_signal(self) -> None:
        email = _make_email(
            sender="noreply@netflix.com",
            subject="Your account",
            body_text="Account update",
        )
        signals = self.parser.parse(email)
        assert len(signals) >= 1

    def test_amount_extraction(self) -> None:
        amounts = EmailParser.extract_amounts("You paid RM 54.00 and $9.99 today")
        assert len(amounts) == 2
        assert ("RM", "54.00") in amounts
        assert ("$", "9.99") in amounts

    def test_amount_extraction_myr(self) -> None:
        amounts = EmailParser.extract_amounts("Total: MYR 120.50")
        assert len(amounts) == 1
        assert amounts[0] == ("MYR", "120.50")

    def test_body_truncated_to_2000(self) -> None:
        long_body = "subscription payment " * 200  # > 2000 chars
        email = _make_email(body_text=long_body)
        signals = self.parser.parse(email)
        for signal in signals:
            if signal.source == "email_body":
                assert len(signal.raw_text) <= 2000

    def test_sender_identification(self) -> None:
        assert self.parser._identify_sender("noreply@spotify.com") == "Spotify"
        assert self.parser._identify_sender("billing@adobe.com") == "Adobe"
        assert self.parser._identify_sender("random@unknown.com") is None
