"""
/mydata handler: exports all data held about a user as structured JSON.
Never exports encrypted password values — only pattern descriptions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog
from src.db.models.cancellation_log import CancellationLog
from src.db.models.oauth_token import OAuthToken
from src.db.models.password_pattern import PasswordPattern
from src.db.models.service_credential import ServiceCredential
from src.db.models.subscription import Subscription
from src.db.models.user import User


class DataExporter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def export_user_data(self, user_id: uuid.UUID) -> dict[str, Any]:
        """Collect all data held about a user into a portable dict."""
        user = await self._session.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")

        subscriptions = (
            await self._session.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
        ).scalars().all()

        oauth_tokens = (
            await self._session.execute(
                select(OAuthToken).where(OAuthToken.user_id == user_id)
            )
        ).scalars().all()

        password_patterns = (
            await self._session.execute(
                select(PasswordPattern).where(PasswordPattern.user_id == user_id)
            )
        ).scalars().all()

        service_credentials = (
            await self._session.execute(
                select(ServiceCredential).where(
                    ServiceCredential.user_id == user_id
                )
            )
        ).scalars().all()

        cancellations = (
            await self._session.execute(
                select(CancellationLog).where(CancellationLog.user_id == user_id)
            )
        ).scalars().all()

        audit_count_result = await self._session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
        )
        audit_entries = audit_count_result.scalars().all()

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user": {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "telegram_username": user.telegram_username,
                "display_name": user.display_name,
                "timezone": user.timezone,
                "created_at": user.created_at.isoformat(),
            },
            "subscriptions": [
                {
                    "service_name": s.service_name,
                    "category": s.category,
                    "amount": str(s.amount),
                    "currency": s.currency,
                    "billing_cycle": s.billing_cycle.value,
                    "next_renewal_date": (
                        s.next_renewal_date.isoformat()
                        if s.next_renewal_date
                        else None
                    ),
                    "status": s.status.value,
                }
                for s in subscriptions
            ],
            "connected_email_providers": [
                {
                    "provider": t.provider,
                    "email": t.email_address,
                    "scopes": t.scopes_granted,
                    "connected_at": t.created_at.isoformat(),
                }
                for t in oauth_tokens
            ],
            "password_patterns": [
                {
                    "bank_name": p.bank_name,
                    "pattern_description": p.pattern_description,
                    # Never export the actual encrypted password
                }
                for p in password_patterns
            ],
            "service_credentials": [
                {
                    "service_name": c.service_name,
                    "auth_method": c.auth_method,
                    # Never export username or password
                }
                for c in service_credentials
            ],
            "cancellation_history": [
                {
                    "service_name": c.service_name,
                    "status": c.status.value,
                    "method": c.method,
                    "saving": (
                        str(c.confirmed_saving_amount)
                        if c.confirmed_saving_amount
                        else None
                    ),
                    "completed_at": (
                        c.completed_at.isoformat() if c.completed_at else None
                    ),
                }
                for c in cancellations
            ],
            "audit_log_entry_count": len(audit_entries),
        }
