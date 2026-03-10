"""Shared helpers for Telegram handlers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from src.db.models.subscription import Subscription
from src.db.repositories.user_repo import UserRepository

if TYPE_CHECKING:
    from src.db.models.user import User


async def get_user_or_reply(update: Update, session: AsyncSession) -> User | None:
    """Resolve Telegram user to DB User. Replies with error if not found."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(update.effective_user.id)
    if user is None:
        await update.message.reply_text("You need to register first. Send /start")
        return None
    return user


def find_by_name(
    subscriptions: Sequence[Subscription], name: str
) -> Subscription | None:
    """Case-insensitive fuzzy match by service name."""
    normalized = name.lower().strip()
    if not normalized:
        return None
    # Exact match first
    for s in subscriptions:
        if s.service_name.lower().strip() == normalized:
            return s
    # Substring match
    for s in subscriptions:
        if normalized in s.service_name.lower() or s.service_name.lower() in normalized:
            return s
    return None
