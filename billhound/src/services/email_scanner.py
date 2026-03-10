"""
Top-level facade: orchestrates the full email → subscription pipeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.oauth_token import OAuthToken
from src.db.repositories.oauth_token_repo import OAuthTokenRepository
from src.email_ingestion.fetchers.gmail_fetcher import GmailFetcher
from src.email_ingestion.fetchers.outlook_fetcher import OutlookFetcher
from src.email_ingestion.oauth.gmail_oauth import GmailOAuthClient
from src.email_ingestion.oauth.outlook_oauth import OutlookOAuthClient
from src.email_ingestion.parser import EmailParser
from src.email_ingestion.types import RawEmail, ScanResult, SubscriptionSignal
from src.llm.base import BaseLLMProvider
from src.pdf.processor import PDFProcessor
from src.services.subscription_service import SubscriptionService

logger = structlog.get_logger()


class EmailScanner:
    """Orchestrates the full email → subscription pipeline for a single user."""

    def __init__(
        self,
        session: AsyncSession,
        token_repo: OAuthTokenRepository,
        sub_service: SubscriptionService,
        email_parser: EmailParser,
        pdf_processor: PDFProcessor,
        llm_provider: BaseLLMProvider,
        gmail_oauth: GmailOAuthClient | None = None,
        outlook_oauth: OutlookOAuthClient | None = None,
    ) -> None:
        self._session = session
        self._token_repo = token_repo
        self._sub_service = sub_service
        self._parser = email_parser
        self._pdf = pdf_processor
        self._llm = llm_provider
        self._gmail_oauth = gmail_oauth
        self._outlook_oauth = outlook_oauth

    async def scan_user(
        self, user_id: uuid.UUID, since: datetime | None = None
    ) -> ScanResult:
        """Full pipeline for one user."""
        result = ScanResult()
        tokens = await self._token_repo.get_by_user(user_id)

        for token in tokens:
            try:
                access_token = await self._ensure_valid_token(token)
                fetcher = self._create_fetcher(token.provider, access_token)
                if not fetcher:
                    continue

                # Fetch emails
                emails = await fetcher.fetch_emails(since=since, max_results=50)
                result.emails_scanned += len(emails)

                # Parse all emails into signals
                all_signals: list[SubscriptionSignal] = []
                for email in emails:
                    signals = self._parser.parse(email)
                    all_signals.extend(signals)

                    # Process PDF attachments
                    for pdf in email.pdf_attachments:
                        pdf_signals = await self._pdf.extract_signals(
                            user_id, pdf
                        )
                        all_signals.extend(pdf_signals)
                        result.pdfs_processed += 1

                # LLM extraction
                if all_signals:
                    extractions = await self._llm.extract_subscriptions(
                        all_signals
                    )

                    # Set source email subject on extractions that don't have one
                    for ext in extractions:
                        if not ext.source_email_subject and emails:
                            ext.source_email_subject = emails[0].subject

                    # Upsert into DB
                    subs, price_changes = (
                        await self._sub_service.upsert_from_extraction(
                            user_id, extractions
                        )
                    )
                    result.price_changes_detected += price_changes

                    # Count new vs updated
                    existing_names = {
                        s.service_name.lower()
                        for s in await self._token_repo._session.run_sync(
                            lambda _: []
                        )
                    } if False else set()  # Simplified: count all as new for MVP
                    result.new_subscriptions += len(subs)

            except Exception:
                logger.exception(
                    "scanner.token_failed",
                    user_id=str(user_id),
                    provider=token.provider,
                )

        logger.info(
            "scanner.completed",
            user_id=str(user_id),
            emails=result.emails_scanned,
            pdfs=result.pdfs_processed,
            new_subs=result.new_subscriptions,
            price_changes=result.price_changes_detected,
        )
        return result

    async def _ensure_valid_token(self, token: OAuthToken) -> str:
        """Check expiry, refresh if needed, return valid access token."""
        if token.token_expiry > datetime.now(timezone.utc):
            return self._token_repo.decrypt_access_token(token)

        # Refresh
        refresh_token = self._token_repo.decrypt_refresh_token(token)

        if token.provider == "gmail" and self._gmail_oauth:
            new_tokens = await self._gmail_oauth.refresh_access_token(
                refresh_token
            )
        elif token.provider == "outlook" and self._outlook_oauth:
            new_tokens = await self._outlook_oauth.refresh_access_token(
                refresh_token
            )
        else:
            raise ValueError(f"Cannot refresh: no OAuth client for {token.provider}")

        new_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=new_tokens.get("expires_in", 3600)
        )

        await self._token_repo.rotate_tokens(
            token,
            new_access_token=new_tokens["access_token"],
            new_refresh_token=new_tokens.get("refresh_token", refresh_token),
            new_expiry=new_expiry,
        )

        return new_tokens["access_token"]

    @staticmethod
    def _create_fetcher(
        provider: str, access_token: str
    ) -> GmailFetcher | OutlookFetcher | None:
        if provider == "gmail":
            return GmailFetcher(access_token)
        elif provider == "outlook":
            return OutlookFetcher(access_token)
        return None
