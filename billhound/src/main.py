"""
Billhound — Application entrypoint.

Boots the full stack in a single async event loop:
  1. PostgreSQL async engine + session factory
  2. OAuth clients (Gmail + Outlook)
  3. LLM provider
  4. Telegram bot (long-polling)
  5. Backfill orchestrator (90-day historical scan on OAuth success)
  6. OAuth callback server (aiohttp on port 8080)
  7. Email scan scheduler (background asyncio task)
  8. ACP listener (optional — Virtuals Agent Commerce Protocol)

Graceful shutdown on SIGINT/SIGTERM with ordered teardown.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys

import structlog

from src.config.logging_config import setup_logging
from src.config.settings import get_settings
from src.db.engine import create_engine, create_session_factory
from src.email_ingestion.oauth.callback_server import OAuthCallbackServer
from src.email_ingestion.oauth.gmail_oauth import GmailOAuthClient
from src.email_ingestion.oauth.outlook_oauth import OutlookOAuthClient
from src.llm.factory import create_llm_provider
from src.services.backfill import BackfillOrchestrator
from src.services.scheduler import EmailScanScheduler
from src.telegram.bot import create_bot_application
from src.trust.encryption import EncryptionService


async def main() -> None:
    setup_logging()
    log = structlog.get_logger()

    settings = get_settings()
    log.info(
        "billhound.starting",
        environment=settings.environment.value,
        app_name=settings.app_name,
    )

    # ── 1. Database ────────────────────────────────────────────────
    engine = create_engine()
    session_factory = create_session_factory(engine)
    encryption = EncryptionService(settings.encryption_key.get_secret_value())

    log.info("billhound.db_connected", pool_size=settings.db_pool_size)

    # ── 2. OAuth clients ───────────────────────────────────────────
    signing_key = settings.encryption_key.get_secret_value()[:32]
    gmail_oauth = GmailOAuthClient(
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret.get_secret_value(),
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/gmail/callback",
        signing_key=signing_key,
    )
    outlook_oauth = OutlookOAuthClient(
        client_id=settings.outlook_client_id,
        client_secret=settings.outlook_client_secret.get_secret_value(),
        redirect_uri=f"{settings.oauth_redirect_base_url}/oauth/outlook/callback",
        signing_key=signing_key,
    )

    # ── 3. LLM provider ───────────────────────────────────────────
    llm_provider = create_llm_provider(settings)

    # ── 4. Telegram bot ────────────────────────────────────────────
    bot_app = create_bot_application(
        token=settings.telegram_bot_token.get_secret_value(),
        session_factory=session_factory,
        settings=settings,
        gmail_oauth=gmail_oauth,
        outlook_oauth=outlook_oauth,
    )
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)

    # ── 5. Backfill orchestrator (90-day historical scan) ──────────
    backfill = BackfillOrchestrator(
        session_factory=session_factory,
        settings=settings,
        encryption=encryption,
        llm_provider=llm_provider,
        gmail_oauth=gmail_oauth,
        outlook_oauth=outlook_oauth,
        telegram_bot=bot_app.bot,
    )

    # ── 6. OAuth callback server (session-per-request + backfill) ──
    callback_server = OAuthCallbackServer(
        gmail_client=gmail_oauth,
        outlook_client=outlook_oauth,
        session_factory=session_factory,
        encryption=encryption,
        backfill=backfill,
    )
    oauth_port = int(os.environ.get("PORT", 8080))
    await callback_server.start(port=oauth_port)

    # ── 7. Email scan scheduler ────────────────────────────────────
    scheduler = EmailScanScheduler(
        session_factory=session_factory,
        settings=settings,
        encryption=encryption,
        llm_provider=llm_provider,
        gmail_oauth=gmail_oauth,
        outlook_oauth=outlook_oauth,
        telegram_bot=bot_app.bot,
    )
    await scheduler.start(interval_minutes=settings.scan_interval_minutes)

    # ── 8. ACP listener (optional, off by default) ────────────────
    acp_client = None
    if settings.acp_enabled:
        from src.acp.actions import CancellationAction
        from src.acp.client import BillhoundACPClient
        from src.acp.listener import ACPJobListener

        loop = asyncio.get_running_loop()
        acp_action = CancellationAction(settings, session_factory, encryption)
        acp_listener = ACPJobListener(acp_action, loop)
        acp_client = BillhoundACPClient(settings, acp_listener.on_new_task)
        acp_client.start()
        log.info("billhound.acp_connected", entity_id=settings.acp_entity_id)

    log.info(
        "billhound.ready",
        message="All subsystems operational",
        services=10,
        oauth_port=oauth_port,
        acp_enabled=settings.acp_enabled,
    )

    # ── Graceful shutdown via signal or KeyboardInterrupt ──────────
    shutdown_event = asyncio.Event()

    # Unix: use loop signal handlers for clean shutdown
    # Windows: fall back to KeyboardInterrupt
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_event.set)

    try:
        if sys.platform == "win32":
            # On Windows, asyncio.Event won't be set by signals,
            # so we rely on KeyboardInterrupt (Ctrl+C)
            while not shutdown_event.is_set():
                await asyncio.sleep(1)
        else:
            await shutdown_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    log.info("billhound.shutting_down")

    # ── Ordered shutdown ───────────────────────────────────────────
    # 1. Stop accepting new Telegram updates
    try:
        await bot_app.updater.stop()
    except Exception:
        log.exception("shutdown.updater_stop_failed")

    # 2. Stop the email scan scheduler
    try:
        await scheduler.stop()
    except Exception:
        log.exception("shutdown.scheduler_stop_failed")

    # 3. Stop the Telegram bot application
    try:
        await bot_app.stop()
        await bot_app.shutdown()
    except Exception:
        log.exception("shutdown.bot_stop_failed")

    # 4. Stop ACP client (if enabled)
    if acp_client:
        try:
            acp_client.stop()
        except Exception:
            log.exception("shutdown.acp_stop_failed")

    # 5. Stop OAuth callback server
    try:
        await callback_server.stop()
    except Exception:
        log.exception("shutdown.callback_server_stop_failed")

    # 6. Dispose of database engine (close all connections)
    try:
        await engine.dispose()
    except Exception:
        log.exception("shutdown.engine_dispose_failed")

    log.info("billhound.stopped")


if __name__ == "__main__":
    asyncio.run(main())
