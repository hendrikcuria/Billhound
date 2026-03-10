"""
PDF text extraction and bank statement parsing using pdfplumber.
"""
from __future__ import annotations

import io
import re
import uuid

import pdfplumber
import structlog

from src.db.repositories.password_pattern_repo import PasswordPatternRepository
from src.email_ingestion.types import PDFAttachment, SubscriptionSignal

logger = structlog.get_logger()

# Common recurring merchant patterns in bank statements
STATEMENT_LINE_PATTERN = re.compile(
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s+"  # Date
    r"(.+?)\s+"                                    # Description/merchant
    r"(RM|MYR|USD|\$)\s*(\d{1,6}[.,]\d{2})",      # Amount
)


class PDFProcessor:
    def __init__(self, password_repo: PasswordPatternRepository) -> None:
        self._password_repo = password_repo

    async def extract_signals(
        self,
        user_id: uuid.UUID,
        attachment: PDFAttachment,
    ) -> list[SubscriptionSignal]:
        """Extract subscription signals from a PDF attachment."""
        text = await self._extract_text(user_id, attachment)
        if not text:
            return []

        return [
            SubscriptionSignal(
                source="pdf_statement",
                raw_text=text[:4000],  # Limit context for LLM
                sender=attachment.sender_email,
                subject=attachment.filename,
            )
        ]

    async def _extract_text(
        self, user_id: uuid.UUID, attachment: PDFAttachment
    ) -> str | None:
        """Try opening PDF, with password fallback."""
        # Try without password first
        text = self._try_open(attachment.content_bytes, password=None)
        if text is not None:
            return text

        # Try passwords from stored patterns
        sender_domain = self._extract_domain(attachment.sender_email)
        patterns = await self._password_repo.get_by_user(user_id)

        for pattern in patterns:
            # Match by domain if possible
            if sender_domain and pattern.sender_email_pattern:
                pattern_domain = self._extract_domain(pattern.sender_email_pattern)
                if pattern_domain and pattern_domain != sender_domain:
                    continue

            password = None
            try:
                password = self._password_repo.decrypt_password(pattern)
                text = self._try_open(attachment.content_bytes, password=password)
                if text is not None:
                    logger.info(
                        "pdf.unlocked",
                        bank=pattern.bank_name,
                        filename=attachment.filename,
                    )
                    return text
            except Exception:
                continue
            finally:
                del password

        logger.warning(
            "pdf.unlock_failed",
            filename=attachment.filename,
            sender=attachment.sender_email,
        )
        return None

    def _try_open(self, pdf_bytes: bytes, password: str | None) -> str | None:
        """Try to open PDF and extract text. Returns None on failure."""
        try:
            stream = io.BytesIO(pdf_bytes)
            try:
                with pdfplumber.open(stream, password=password) as pdf:
                    pages_text = []
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            pages_text.append(page_text)
                    return "\n".join(pages_text) if pages_text else None
            finally:
                stream.close()
        except Exception:
            return None

    @staticmethod
    def _extract_domain(email: str) -> str | None:
        """Extract domain from email address."""
        if "@" in email:
            return email.split("@")[-1].lower().strip()
        return None

    @staticmethod
    def parse_statement_lines(text: str) -> list[dict]:
        """Parse bank statement text for transaction lines. Utility for tests."""
        results = []
        for match in STATEMENT_LINE_PATTERN.finditer(text):
            results.append({
                "date": match.group(1),
                "description": match.group(2).strip(),
                "currency": match.group(3),
                "amount": match.group(4),
            })
        return results
