"""
Periodic email scan scheduler. Runs as an asyncio background task.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import Settings
from src.db.models.oauth_token import OAuthToken
from src.db.repositories.oauth_token_repo import OAuthTokenRepository
from src.db.repositories.password_pattern_repo import PasswordPatternRepository
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.email_ingestion.oauth.gmail_oauth import GmailOAuthClient
from src.email_ingestion.oauth.outlook_oauth import OutlookOAuthClient
from src.email_ingestion.parser import EmailParser
from src.llm.base import BaseLLMProvider
from src.pdf.processor import PDFProcessor
from src.services.email_scanner import EmailScanner
from src.services.subscription_service import SubscriptionService
from src.trust.audit import AuditWriter
from src.trust.encryption import EncryptionService

logger = structlog.get_logger()


class EmailScanScheduler:
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
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self, interval_minutes: int = 60) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop(interval_minutes))
        logger.info("scheduler.started", interval_minutes=interval_minutes)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("scheduler.stopped")

    async def _run_loop(self, interval_minutes: int) -> None:
        while self._running:
            try:
                await self._scan_all_users()
            except Exception:
                logger.exception("scheduler.scan_failed")
            await asyncio.sleep(interval_minutes * 60)

    async def _scan_all_users(self) -> None:
        """Scan all users with active OAuth tokens."""
        async with self._session_factory() as session:
            # Get distinct user_ids with OAuth tokens
            result = await session.execute(
                select(OAuthToken.user_id).distinct()
            )
            user_ids = [row[0] for row in result.all()]

        logger.info("scheduler.scanning", user_count=len(user_ids))

        for user_id in user_ids:
            async with self._session_factory() as session:
                try:
                    scanner = self._build_scanner(session)
                    since = datetime.now(timezone.utc) - timedelta(
                        minutes=self._settings.scan_interval_minutes
                    )
                    scan_result = await scanner.scan_user(user_id, since=since)
                    await session.commit()
                    logger.info(
                        "scheduler.user_scanned",
                        user_id=str(user_id),
                        emails=scan_result.emails_scanned,
                        new_subs=scan_result.new_subscriptions,
                    )

                    # Post-scan alert hook
                    if self._telegram_bot:
                        try:
                            from src.services.alert_service import AlertService

                            alert_svc = AlertService(
                                session, self._telegram_bot, self._settings
                            )
                            alerts = await alert_svc.check_and_send_for_user(user_id)
                            if alerts:
                                await session.commit()
                                logger.info(
                                    "scheduler.alerts_sent",
                                    user_id=str(user_id),
                                    count=alerts,
                                )
                        except Exception:
                            logger.exception(
                                "scheduler.alert_check_failed",
                                user_id=str(user_id),
                            )
                except Exception:
                    logger.exception(
                        "scheduler.user_failed", user_id=str(user_id)
                    )

    def _build_scanner(self, session: AsyncSession) -> EmailScanner:
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
