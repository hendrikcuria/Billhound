"""
Extract subscription signals from raw email content.
Rule-based keyword matching — no LLM needed at this stage.
"""
from __future__ import annotations

import re

from src.email_ingestion.types import RawEmail, SubscriptionSignal

SUBSCRIPTION_KEYWORDS = [
    "subscription", "receipt", "invoice", "payment",
    "renewal", "billing", "statement", "trial",
    "your plan", "monthly charge", "annual charge",
    "auto-renewal", "recurring", "membership",
]

KNOWN_SENDERS: dict[str, str] = {
    "netflix.com": "Netflix",
    "spotify.com": "Spotify",
    "apple.com": "Apple",
    "google.com": "Google",
    "adobe.com": "Adobe",
    "microsoft.com": "Microsoft",
    "amazon.com": "Amazon",
    "disney.com": "Disney+",
    "hulu.com": "Hulu",
    "dropbox.com": "Dropbox",
    "notion.so": "Notion",
    "canva.com": "Canva",
    "zoom.us": "Zoom",
    "slack.com": "Slack",
    "github.com": "GitHub",
    "openai.com": "OpenAI",
    "nordvpn.com": "NordVPN",
    "expressvpn.com": "ExpressVPN",
    "grab.com": "Grab",
    "foodpanda.com": "foodpanda",
}

# Matches: RM 54.00, RM54.00, MYR 54.00, $9.99, USD 12.00, EUR 5.00
AMOUNT_PATTERN = re.compile(
    r"(RM|MYR|USD|EUR|GBP|SGD|\$|€|£)\s*(\d{1,6}[.,]\d{2})",
    re.IGNORECASE,
)


class EmailParser:
    """Extract subscription signals from raw emails."""

    def parse(self, email: RawEmail) -> list[SubscriptionSignal]:
        signals: list[SubscriptionSignal] = []

        # Check subject for subscription keywords
        if self._matches_keywords(email.subject):
            signals.append(
                SubscriptionSignal(
                    source="email_subject",
                    raw_text=email.subject,
                    sender=email.sender,
                    subject=email.subject,
                )
            )

        # Check body for amount patterns + keywords
        if self._matches_keywords(email.body_text) or self._has_amount(email.body_text):
            signals.append(
                SubscriptionSignal(
                    source="email_body",
                    raw_text=email.body_text[:2000],  # Limit context size
                    sender=email.sender,
                    subject=email.subject,
                )
            )

        # Known sender — always treat as a signal
        sender_name = self._identify_sender(email.sender)
        if sender_name and not signals:
            signals.append(
                SubscriptionSignal(
                    source="email_subject",
                    raw_text=f"{sender_name}: {email.subject}",
                    sender=email.sender,
                    subject=email.subject,
                )
            )

        return signals

    def _matches_keywords(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in SUBSCRIPTION_KEYWORDS)

    def _has_amount(self, text: str) -> bool:
        return bool(AMOUNT_PATTERN.search(text))

    def _identify_sender(self, sender_email: str) -> str | None:
        """Match sender domain against known subscription services."""
        lower = sender_email.lower()
        for domain, name in KNOWN_SENDERS.items():
            if domain in lower:
                return name
        return None

    @staticmethod
    def extract_amounts(text: str) -> list[tuple[str, str]]:
        """Find currency+amount pairs in text. Public for use by PDF processor."""
        return AMOUNT_PATTERN.findall(text)
