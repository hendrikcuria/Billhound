"""
Fetch emails from Outlook/Microsoft 365 via Microsoft Graph API.
Endpoint: GET https://graph.microsoft.com/v1.0/me/messages
"""
from __future__ import annotations

import base64
from datetime import datetime
from html.parser import HTMLParser

import aiohttp
import structlog

from src.email_ingestion.types import PDFAttachment, RawEmail

logger = structlog.get_logger()

SUBSCRIPTION_FILTER_TERMS = [
    "subscription", "receipt", "invoice", "payment",
    "renewal", "billing", "statement",
]


class _HTMLStripper(HTMLParser):
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


class OutlookFetcher:
    BASE_URL = "https://graph.microsoft.com/v1.0/me"

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
        params: dict[str, str | int] = {
            "$top": max_results,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,body,hasAttachments",
        }

        # Build OData filter
        filters: list[str] = []
        if since:
            iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            filters.append(f"receivedDateTime ge {iso}")

        if sender_filter:
            # Backfill mode: query only known merchant senders
            sender_clauses = " or ".join(
                f"from/emailAddress/address eq '{addr}'" for addr in sender_filter
            )
            filters.append(f"({sender_clauses})")
        else:
            subject_filters = " or ".join(
                f"contains(subject,'{term}')" for term in SUBSCRIPTION_FILTER_TERMS
            )
            filters.append(f"({subject_filters})")
        params["$filter"] = " and ".join(filters)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/messages",
                headers=self._headers(),
                params=params,
            ) as resp:
                if resp.status != 200:
                    logger.error("outlook.list_failed", status=resp.status)
                    return []
                data = await resp.json()

            messages = data.get("value", [])
            results: list[RawEmail] = []

            for msg in messages:
                raw = await self._build_raw_email(session, msg)
                results.append(raw)

            return results

    async def _build_raw_email(
        self, session: aiohttp.ClientSession, msg: dict
    ) -> RawEmail:
        sender_data = msg.get("from", {}).get("emailAddress", {})
        sender = sender_data.get("address", "")

        body = msg.get("body", {})
        body_text = body.get("content", "")
        if body.get("contentType") == "html":
            body_text = _strip_html(body_text)

        pdf_attachments: list[PDFAttachment] = []
        if msg.get("hasAttachments"):
            pdf_attachments = await self._get_pdf_attachments(
                session, msg["id"], sender
            )

        return RawEmail(
            message_id=msg["id"],
            subject=msg.get("subject", ""),
            sender=sender,
            body_text=body_text,
            received_at=msg.get("receivedDateTime", ""),
            pdf_attachments=pdf_attachments,
        )

    async def _get_pdf_attachments(
        self,
        session: aiohttp.ClientSession,
        message_id: str,
        sender: str,
    ) -> list[PDFAttachment]:
        async with session.get(
            f"{self.BASE_URL}/messages/{message_id}/attachments",
            headers=self._headers(),
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        attachments: list[PDFAttachment] = []
        for att in data.get("value", []):
            content_type = att.get("contentType", "")
            if "pdf" in content_type.lower() and att.get("contentBytes"):
                attachments.append(
                    PDFAttachment(
                        filename=att.get("name", "attachment.pdf"),
                        content_bytes=base64.b64decode(att["contentBytes"]),
                        sender_email=sender,
                    )
                )
        return attachments
