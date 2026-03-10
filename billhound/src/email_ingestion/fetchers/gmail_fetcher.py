"""
Fetch emails from Gmail using REST API (no SDK).
Endpoints:
  - List: GET /gmail/v1/users/me/messages?q=...
  - Get:  GET /gmail/v1/users/me/messages/{id}?format=full
  - Attachment: GET /gmail/v1/users/me/messages/{id}/attachments/{attachId}
"""
from __future__ import annotations

import base64
from datetime import datetime
from html.parser import HTMLParser

import aiohttp
import structlog

from src.email_ingestion.types import PDFAttachment, RawEmail

logger = structlog.get_logger()

SUBSCRIPTION_QUERY_TERMS = (
    "subject:subscription OR subject:receipt OR subject:invoice "
    "OR subject:payment OR subject:renewal OR subject:billing "
    "OR subject:statement"
)


class _HTMLStripper(HTMLParser):
    """Minimal HTML → plaintext converter."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


class GmailFetcher:
    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def fetch_emails(
        self,
        *,
        since: datetime | None = None,
        max_results: int = 50,
        sender_filter: list[str] | None = None,
    ) -> list[RawEmail]:
        if sender_filter:
            # Backfill mode: query only known merchant senders
            from_clauses = " OR ".join(f"from:{addr}" for addr in sender_filter)
            query = f"({from_clauses})"
        else:
            query = SUBSCRIPTION_QUERY_TERMS
        if since:
            epoch = int(since.timestamp())
            query = f"after:{epoch} ({query})"

        async with aiohttp.ClientSession() as session:
            # List message IDs
            async with session.get(
                f"{self.BASE_URL}/messages",
                headers=self._headers(),
                params={"q": query, "maxResults": max_results},
            ) as resp:
                if resp.status != 200:
                    logger.error("gmail.list_failed", status=resp.status)
                    return []
                data = await resp.json()

            messages = data.get("messages", [])
            results: list[RawEmail] = []

            for msg_ref in messages:
                raw = await self._get_message(session, msg_ref["id"])
                if raw:
                    results.append(raw)

            return results

    async def _get_message(
        self, session: aiohttp.ClientSession, message_id: str
    ) -> RawEmail | None:
        async with session.get(
            f"{self.BASE_URL}/messages/{message_id}",
            headers=self._headers(),
            params={"format": "full"},
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

        headers = {
            h["name"].lower(): h["value"]
            for h in data.get("payload", {}).get("headers", [])
        }
        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        received = headers.get("date", "")

        body_text = ""
        pdf_attachments: list[PDFAttachment] = []

        self._extract_parts(
            session, message_id, data.get("payload", {}),
            body_text_parts := [],
            pdf_refs := [],
        )
        body_text = "\n".join(body_text_parts)

        # Download PDF attachments
        for att_id, filename in pdf_refs:
            pdf_bytes = await self._get_attachment(session, message_id, att_id)
            if pdf_bytes:
                pdf_attachments.append(
                    PDFAttachment(
                        filename=filename,
                        content_bytes=pdf_bytes,
                        sender_email=sender,
                    )
                )

        return RawEmail(
            message_id=message_id,
            subject=subject,
            sender=sender,
            body_text=body_text,
            received_at=received,
            pdf_attachments=pdf_attachments,
        )

    def _extract_parts(
        self,
        session: aiohttp.ClientSession,
        message_id: str,
        part: dict,
        text_parts: list[str],
        pdf_refs: list[tuple[str, str]],
    ) -> None:
        """Recursively extract text body and PDF attachment refs from MIME parts."""
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})

        if mime_type == "text/plain" and "data" in body:
            decoded = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")
            text_parts.append(decoded)
        elif mime_type == "text/html" and "data" in body and not text_parts:
            decoded = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="replace")
            text_parts.append(_strip_html(decoded))
        elif mime_type == "application/pdf" and body.get("attachmentId"):
            filename = part.get("filename", "attachment.pdf")
            pdf_refs.append((body["attachmentId"], filename))

        for sub_part in part.get("parts", []):
            self._extract_parts(session, message_id, sub_part, text_parts, pdf_refs)

    async def _get_attachment(
        self, session: aiohttp.ClientSession, message_id: str, attachment_id: str
    ) -> bytes | None:
        async with session.get(
            f"{self.BASE_URL}/messages/{message_id}/attachments/{attachment_id}",
            headers=self._headers(),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return base64.urlsafe_b64decode(data.get("data", ""))
