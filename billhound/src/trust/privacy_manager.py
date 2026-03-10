"""
Privacy manager: top-level facade for the trust module.
Orchestrates data export and account deletion.

This is the standalone reusable component — zero imports from
telegram, email_ingestion, or automation packages.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.trust.account_deletion import AccountDeletionService
from src.trust.audit import AuditWriter
from src.trust.consent import ConsentTracker
from src.trust.data_export import DataExporter


class PrivacyManager:
    """Top-level facade for the trust module."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditWriter(session)
        self._exporter = DataExporter(session)
        self._deletion = AccountDeletionService(session, self._audit)
        self._consent = ConsentTracker(self._audit)

    @property
    def consent(self) -> ConsentTracker:
        return self._consent

    @property
    def audit(self) -> AuditWriter:
        return self._audit

    async def export_my_data(self, user_id: uuid.UUID) -> dict:
        """Export all user data (/mydata command)."""
        data = await self._exporter.export_user_data(user_id)
        await self._audit.log(
            action="data_exported",
            user_id=user_id,
        )
        return data

    async def delete_account(self, user_id: uuid.UUID) -> dict:
        """Full account deletion (/deleteaccount command)."""
        return await self._deletion.delete_account(user_id)
