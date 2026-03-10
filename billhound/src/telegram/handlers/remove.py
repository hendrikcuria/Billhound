"""Cancellation handler. User sends "cancel <service_name>".

If Playwright automation is available for the service and settings
are present, attempts browser-based cancellation first. Falls back
to manual confirmation if automation fails.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import CancellationStatus, SubscriptionStatus
from src.db.repositories.cancellation_log_repo import CancellationLogRepository
from src.db.repositories.service_credential_repo import ServiceCredentialRepository
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.telegram.formatting import (
    annualize,
    format_billing_cycle,
    format_currency,
)
from src.telegram.handlers._common import find_by_name, get_user_or_reply
from src.trust.audit import AuditWriter
from src.trust.encryption import EncryptionService

logger = structlog.get_logger()

CANCEL_PATTERN = re.compile(r"^cancel\s+(.+)$", re.IGNORECASE)


async def remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    match = CANCEL_PATTERN.match(text)
    if not match:
        return

    service_name = match.group(1).strip()
    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return

        sub_repo = SubscriptionRepository(session)
        existing = await sub_repo.get_active_by_user(user.id)
        target = find_by_name(existing, service_name)

        if not target:
            await update.message.reply_text(
                f'No active subscription found matching "{service_name}"'
            )
            return

        cancel_repo = CancellationLogRepository(session)
        audit = AuditWriter(session)

        # ── Attempt Playwright automation if settings are present ──
        settings = context.bot_data.get("settings")
        if settings:
            from src.automation import CancellationOrchestrator, has_strategy
            from src.automation.auth.base_auth_strategy import DecryptedCredential

            if has_strategy(target.service_name):
                log_entry = await cancel_repo.create(
                    user_id=user.id,
                    subscription_id=target.id,
                    service_name=target.service_name,
                    status=CancellationStatus.INITIATED,
                    method="playwright",
                )
                await session.commit()

                await update.message.reply_text(
                    f"Attempting to cancel {target.service_name} automatically..."
                )

                # Look up stored credentials for this service
                credential = None
                encryption = EncryptionService(
                    settings.encryption_key.get_secret_value()
                )
                cred_repo = ServiceCredentialRepository(session, encryption)
                stored_cred = await cred_repo.get_by_service(
                    user.id, target.service_name
                )
                if stored_cred:
                    try:
                        credential = DecryptedCredential(
                            username=cred_repo.decrypt_username(stored_cred),
                            password=cred_repo.decrypt_password(stored_cred),
                            service_name=target.service_name,
                        )
                    except Exception:
                        logger.warning(
                            "automation.credential_decrypt_failed",
                            service=target.service_name,
                        )

                orchestrator = CancellationOrchestrator(
                    headless=settings.playwright_headless,
                    timeout_ms=settings.playwright_timeout_ms,
                    screenshot_dir=settings.screenshot_dir,
                )
                try:
                    result = await orchestrator.cancel(
                        target, credential=credential
                    )
                finally:
                    credential = None

                if result.success:
                    await sub_repo.update(
                        target, status=SubscriptionStatus.CANCELLED
                    )
                    annual_saving = annualize(target.amount, target.billing_cycle)
                    await cancel_repo.update(
                        log_entry,
                        status=CancellationStatus.SUCCESS,
                        screenshot_path=result.screenshot_path,
                        confirmed_saving_amount=target.amount,
                        confirmed_saving_currency=target.currency,
                        completed_at=datetime.now(timezone.utc),
                    )
                    await audit.log(
                        action="subscription_cancelled",
                        user_id=user.id,
                        entity_type="subscription",
                        entity_id=str(target.id),
                        details={"method": "playwright"},
                    )
                    await session.commit()

                    total_savings = await cancel_repo.get_monthly_savings(user.id)
                    await update.message.reply_text(
                        f"Successfully cancelled {target.service_name}\n"
                        f"Confirmed saving: {format_currency(target.amount)}"
                        f"{format_billing_cycle(target.billing_cycle)} "
                        f"({format_currency(annual_saving)}/year)\n"
                        f"Total savings this month: {format_currency(total_savings)}"
                    )
                    return
                else:
                    await cancel_repo.update(
                        log_entry,
                        status=result.status,
                        screenshot_path=result.screenshot_path,
                        error_message=result.error_message,
                    )
                    await session.commit()

                    fallback_msg = (
                        f"I couldn't cancel {target.service_name} automatically.\n"
                    )
                    if result.fallback_url:
                        fallback_msg += (
                            f"You can cancel manually here: {result.fallback_url}\n"
                        )
                    fallback_msg += (
                        "The subscription is still active. "
                        f'Send "cancel {target.service_name.lower()}" again '
                        "after you've cancelled manually."
                    )
                    await update.message.reply_text(fallback_msg)
                    return

        # ── Manual telegram cancel (no automation available) ──
        await sub_repo.update(target, status=SubscriptionStatus.CANCELLED)

        annual_saving = annualize(target.amount, target.billing_cycle)
        await cancel_repo.create(
            user_id=user.id,
            subscription_id=target.id,
            service_name=target.service_name,
            status=CancellationStatus.SUCCESS,
            method="user_telegram",
            confirmed_saving_amount=target.amount,
            confirmed_saving_currency=target.currency,
            completed_at=datetime.now(timezone.utc),
        )

        total_savings = await cancel_repo.get_monthly_savings(user.id)

        await audit.log(
            action="subscription_cancelled",
            user_id=user.id,
            entity_type="subscription",
            entity_id=str(target.id),
        )
        await session.commit()

    await update.message.reply_text(
        f"Cancelled {target.service_name}\n"
        f"Confirmed saving: {format_currency(target.amount)}"
        f"{format_billing_cycle(target.billing_cycle)} "
        f"({format_currency(annual_saving)}/year)\n"
        f"Total savings this month: {format_currency(total_savings)}"
    )
