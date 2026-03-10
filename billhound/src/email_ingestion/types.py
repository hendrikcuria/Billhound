"""
In-memory data types for the email ingestion pipeline.
These are never persisted — they exist only during processing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PDFAttachment:
    """PDF attachment bytes. Never persisted."""

    filename: str
    content_bytes: bytes
    sender_email: str


@dataclass(frozen=True)
class RawEmail:
    """Raw email fetched from provider. Never persisted."""

    message_id: str
    subject: str
    sender: str
    body_text: str
    received_at: str  # ISO format
    pdf_attachments: list[PDFAttachment] = field(default_factory=list)


@dataclass(frozen=True)
class SubscriptionSignal:
    """Intermediate signal extracted from email/PDF before LLM processing."""

    source: str  # "email_subject", "email_body", "pdf_statement"
    raw_text: str
    sender: str
    subject: str | None = None


@dataclass
class ExtractedSubscription:
    """Structured output from LLM extraction."""

    service_name: str
    amount: Decimal
    currency: str = "MYR"
    billing_cycle: str = "monthly"
    next_renewal_date: date | None = None
    trial_end_date: date | None = None
    confidence_score: float = 0.0
    source_email_subject: str | None = None
    cancellation_url: str | None = None
    category: str | None = None


@dataclass
class ScanResult:
    """Summary of a single user scan."""

    emails_scanned: int = 0
    pdfs_processed: int = 0
    new_subscriptions: int = 0
    updated_subscriptions: int = 0
    price_changes_detected: int = 0
