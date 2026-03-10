"""Add subscription via guided FSM (ConversationHandler).

Flow:
  1. User clicks [Add Subscription] button
  2. Bot asks for service name
  3. User types name
  4. Bot asks for amount
  5. User types amount
  6. Bot shows billing cycle buttons
  7. User clicks cycle → subscription created
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.config.constants import BillingCycle, SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.db.repositories.user_repo import UserRepository
from src.services.merchant_db import lookup_category
from src.telegram.formatting import format_billing_cycle, format_currency
from src.trust.audit import AuditWriter

logger = structlog.get_logger()

# FSM states
AWAITING_NAME, AWAITING_AMOUNT, AWAITING_CYCLE = range(3)

CYCLE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Weekly", callback_data="cycle_weekly"),
        InlineKeyboardButton("Monthly", callback_data="cycle_monthly"),
    ],
    [
        InlineKeyboardButton("Quarterly", callback_data="cycle_quarterly"),
        InlineKeyboardButton("Annual", callback_data="cycle_annual"),
    ],
])

_CYCLE_MAP = {
    "cycle_weekly": BillingCycle.WEEKLY,
    "cycle_monthly": BillingCycle.MONTHLY,
    "cycle_quarterly": BillingCycle.QUARTERLY,
    "cycle_annual": BillingCycle.ANNUAL,
}


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: user clicked [Add Subscription] button."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Let's add a subscription.\n\n"
        "What's the name of the service?\n"
        "(e.g. Netflix, Spotify, Gym)"
    )
    return AWAITING_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: receive service name."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Please enter a service name:")
        return AWAITING_NAME

    context.user_data["add_service_name"] = name
    await update.message.reply_text(
        f"Got it \u2014 {name}.\n\n"
        "How much per billing cycle?\n"
        "Example: 54 or RM54.00"
    )
    return AWAITING_AMOUNT


async def add_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: receive amount."""
    raw = update.message.text.strip()
    # Strip "RM" prefix if present
    raw = re.sub(r"^RM\s*", "", raw, flags=re.IGNORECASE)

    try:
        amount = Decimal(raw)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (InvalidOperation, ValueError):
        await update.message.reply_text(
            "That doesn't look like a valid amount.\n"
            "Please enter a number, e.g. 54 or RM54.00"
        )
        return AWAITING_AMOUNT

    context.user_data["add_amount"] = amount
    name = context.user_data["add_service_name"]
    await update.message.reply_text(
        f"{name} \u2014 {format_currency(amount)}\n\n"
        "What's the billing cycle?",
        reply_markup=CYCLE_KEYBOARD,
    )
    return AWAITING_CYCLE


async def add_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: receive billing cycle from inline button, create subscription."""
    query = update.callback_query
    await query.answer()

    cycle = _CYCLE_MAP.get(query.data, BillingCycle.MONTHLY)
    service_name = context.user_data.pop("add_service_name", "Unknown")
    amount = context.user_data.pop("add_amount", Decimal("0"))

    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if not user:
            await query.message.reply_text(
                "You need to register first. Send /start"
            )
            return ConversationHandler.END

        sub_repo = SubscriptionRepository(session)
        existing = await sub_repo.get_active_by_user(user.id)
        normalized = service_name.lower().strip()

        for s in existing:
            if s.service_name.lower().strip() == normalized:
                await query.message.reply_text(
                    f"{service_name} already exists at "
                    f"{format_currency(s.amount)}"
                    f"{format_billing_cycle(s.billing_cycle)}"
                )
                return ConversationHandler.END

        category = lookup_category(service_name)
        sub = await sub_repo.create(
            user_id=user.id,
            service_name=service_name,
            category=category,
            amount=amount,
            currency="MYR",
            billing_cycle=cycle,
            status=SubscriptionStatus.ACTIVE,
            confidence_score=Decimal("1.00"),
            is_manually_added=True,
        )

        audit = AuditWriter(session)
        await audit.log(
            action="subscription_added_manually",
            user_id=user.id,
            entity_type="subscription",
            entity_id=str(sub.id),
            details={"service": service_name, "amount": str(amount)},
        )
        await session.commit()

    await query.message.reply_text(
        f"\u2705 Added {service_name} \u2014 "
        f"{format_currency(amount)}{format_billing_cycle(cycle)}"
    )
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the add flow via /cancel command."""
    context.user_data.pop("add_service_name", None)
    context.user_data.pop("add_amount", None)
    if update.message:
        await update.message.reply_text("Subscription add cancelled.")
    return ConversationHandler.END


def build_add_subscription_conversation() -> ConversationHandler:
    """Build the FSM for guided subscription addition."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_start, pattern=r"^add_subscription$"),
        ],
        states={
            AWAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_name),
            ],
            AWAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount),
            ],
            AWAITING_CYCLE: [
                CallbackQueryHandler(add_cycle, pattern=r"^cycle_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )
