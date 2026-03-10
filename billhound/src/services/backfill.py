"""
Historical backfill orchestrator.

Triggered on OAuth success to scan the last 90 days of email from known
merchant senders, extract subscriptions, and deliver an instant summary
to the user via Telegram.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.repositories.oauth_token_repo import OAuthTokenRepository
from src.db.repositories.password_pattern_repo import PasswordPatternRepository
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.db.repositories.user_repo import UserRepository
from src.email_ingestion.oauth.gmail_oauth import GmailOAuthClient
from src.email_ingestion.oauth.outlook_oauth import OutlookOAuthClient
from src.email_ingestion.parser import EmailParser
from src.llm.base import BaseLLMProvider
from src.pdf.processor import PDFProcessor
from src.services.email_scanner import EmailScanner
from src.services.subscription_service import SubscriptionService
from src.telegram.formatting import format_currency, to_monthly
from src.trust.audit import AuditWriter
from src.trust.encryption import EncryptionService

logger = structlog.get_logger()


@dataclass
class BackfillResult:
    """Summary of a historical backfill run."""

    subscriptions_found: int = 0
    total_monthly: Decimal = Decimal("0.00")
    emails_scanned: int = 0


class BackfillOrchestrator:
    """90-day historical email scan triggered on OAuth success.

    Reuses the full EmailScanner pipeline (token refresh → fetch → parse →
    PDF → LLM → upsert) with a 90-day lookback window.  After the scan,
    sends a Telegram summary to the user.
    """

    LOOKBACK_DAYS = 90
    BATCH_SIZE = 25  # emails per API call (rate-limit-friendly)

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        encryption: EncryptionService,
        llm_provider: BaseLLMProvider,
        gmail_oauth: GmailOAuthClient | None = None,
        outlook_oauth: OutlookOAuthClient | None = None,
        telegram_bot: object | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._encryption = encryption
        self._llm = llm_provider
        self._gmail_oauth = gmail_oauth
        self._outlook_oauth = outlook_oauth
        self._telegram_bot = telegram_bot

    async def run_backfill(
        self, user_id: uuid.UUID, provider: str
    ) -> BackfillResult:
        """Execute a 90-day historical scan for *provider* and send summary."""
        since = datetime.now(timezone.utc) - timedelta(days=self.LOOKBACK_DAYS)

        logger.info(
            "backfill.started",
            user_id=str(user_id),
            provider=provider,
            since=since.isoformat(),
        )

        async with self._session_factory() as session:
            scanner = self._build_scanner(session)
            scan_result = await scanner.scan_user(user_id, since=since)
            await session.commit()

            # Build summary from the user's current active subscriptions
            sub_repo = SubscriptionRepository(session)
            active_subs = await sub_repo.get_active_by_user(user_id)

            total_monthly = sum(
                (to_monthly(s.amount, s.billing_cycle) for s in active_subs),
                Decimal("0.00"),
            )

            result = BackfillResult(
                subscriptions_found=len(active_subs),
                total_monthly=total_monthly,
                emails_scanned=scan_result.emails_scanned,
            )

            # Send Telegram summary
            if self._telegram_bot:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_id(user_id)
                if user:
                    await self._send_summary(
                        user.telegram_id, result
                    )

        logger.info(
            "backfill.completed",
            user_id=str(user_id),
            provider=provider,
            subscriptions=result.subscriptions_found,
            monthly_total=str(result.total_monthly),
            emails=result.emails_scanned,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_scanner(self, session: AsyncSession) -> EmailScanner:
        """Construct an EmailScanner with all deps — same pattern as scheduler."""
        token_repo = OAuthTokenRepository(session, self._encryption)
        sub_repo = SubscriptionRepository(session)
        password_repo = PasswordPatternRepository(session, self._encryption)
        audit = AuditWriter(session)

        return EmailScanner(
            session=session,
            token_repo=token_repo,
            sub_service=SubscriptionService(
                session, sub_repo, audit, self._settings.confidence_threshold
            ),
            email_parser=EmailParser(),
            pdf_processor=PDFProcessor(password_repo),
            llm_provider=self._llm,
            gmail_oauth=self._gmail_oauth,
            outlook_oauth=self._outlook_oauth,
        )

    async def _send_summary(
        self,
        telegram_id: int,
        result: BackfillResult,
    ) -> None:
        """Send the backfill completion summary to the user."""
        formatted_total = format_currency(result.total_monthly)

        if result.subscriptions_found == 0:
            message = (
                "\U0001f4ca Initial scan complete.\n"
                "No active subscriptions found in your recent emails.\n\n"
                "Tip: Use /add to manually add subscriptions."
            )
        else:
            sub_word = (
                "subscription" if result.subscriptions_found == 1 else "subscriptions"
            )
            message = (
                f"\U0001f4ca Initial scan complete.\n"
                f"Found {result.subscriptions_found} active {sub_word} "
                f"totaling {formatted_total}/month.\n\n"
                f"Use /subscriptions to see your full ledger."
            )

        try:
            await self._telegram_bot.send_message(  # type: ignore[union-attr]
                chat_id=telegram_id, text=message
            )
        except Exception:
            logger.exception(
                "backfill.telegram_send_failed", telegram_id=telegram_id
            )
