"""
Unit tests for the trust module: audit writer, data export, account deletion.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog
from src.db.models.user import User
from src.trust.audit import AuditWriter
from src.trust.consent import ConsentTracker
from src.trust.data_export import DataExporter
from src.trust.oauth_scope_display import format_scope_display
from src.trust.privacy_manager import PrivacyManager
from tests.factories import make_subscription, make_user


class TestAuditWriter:
    @pytest.mark.asyncio
    async def test_log_creates_entry(self, session: AsyncSession) -> None:
        writer = AuditWriter(session)
        entry = await writer.log(
            action="test_action",
            details={"key": "value"},
        )
        assert entry.action == "test_action"
        assert entry.details == {"key": "value"}
        assert entry.created_at is not None

    @pytest.mark.asyncio
    async def test_log_with_user_id(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=111111)
        session.add(user)
        await session.flush()

        writer = AuditWriter(session)
        entry = await writer.log(
            action="user_action",
            user_id=user.id,
            entity_type="user",
            entity_id=str(user.id),
        )
        assert entry.user_id == user.id
        assert entry.entity_type == "user"


class TestConsentTracker:
    @pytest.mark.asyncio
    async def test_record_grant(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=222222)
        session.add(user)
        await session.flush()

        audit = AuditWriter(session)
        consent = ConsentTracker(audit)
        await consent.record_grant(
            user_id=user.id,
            provider="gmail",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            email="test@gmail.com",
        )

        result = await session.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "oauth_granted",
            )
        )
        entry = result.scalar_one()
        assert entry.details["provider"] == "gmail"

    @pytest.mark.asyncio
    async def test_record_revocation(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=333333)
        session.add(user)
        await session.flush()

        audit = AuditWriter(session)
        consent = ConsentTracker(audit)
        await consent.record_revocation(
            user_id=user.id,
            provider="outlook",
            email="test@outlook.com",
        )

        result = await session.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "oauth_revoked",
            )
        )
        entry = result.scalar_one()
        assert entry.details["provider"] == "outlook"


class TestDataExporter:
    @pytest.mark.asyncio
    async def test_export_user_data(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=444444)
        session.add(user)
        await session.flush()

        sub = make_subscription(user.id, service_name="Spotify")
        session.add(sub)
        await session.flush()

        exporter = DataExporter(session)
        data = await exporter.export_user_data(user.id)

        assert data["user"]["telegram_id"] == 444444
        assert len(data["subscriptions"]) == 1
        assert data["subscriptions"][0]["service_name"] == "Spotify"
        assert "exported_at" in data

    @pytest.mark.asyncio
    async def test_export_nonexistent_user(self, session: AsyncSession) -> None:
        exporter = DataExporter(session)
        with pytest.raises(ValueError, match="not found"):
            await exporter.export_user_data(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_export_never_includes_passwords(
        self, session: AsyncSession
    ) -> None:
        user = make_user(telegram_id=555555)
        session.add(user)
        await session.flush()

        from tests.factories import make_password_pattern

        pattern = make_password_pattern(user.id)
        session.add(pattern)
        await session.flush()

        exporter = DataExporter(session)
        data = await exporter.export_user_data(user.id)

        for p in data["password_patterns"]:
            assert "password_encrypted" not in p
            assert "bank_name" in p
            assert "pattern_description" in p


class TestPrivacyManager:
    @pytest.mark.asyncio
    async def test_export_my_data_logs_audit(
        self, session: AsyncSession
    ) -> None:
        user = make_user(telegram_id=666666)
        session.add(user)
        await session.flush()

        pm = PrivacyManager(session)
        data = await pm.export_my_data(user.id)

        assert data["user"]["telegram_id"] == 666666

        # Verify audit log entry was created
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "data_exported",
            )
        )
        assert result.scalar_one() is not None

    @pytest.mark.asyncio
    async def test_delete_account(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=777777)
        session.add(user)
        await session.flush()
        user_id = user.id

        pm = PrivacyManager(session)
        result = await pm.delete_account(user_id)

        assert result["deleted"] is True
        assert result["user_id"] == str(user_id)

        # User should be gone
        deleted = await session.get(User, user_id)
        assert deleted is None


class TestOAuthScopeDisplay:
    def test_gmail_scope_display(self) -> None:
        text = format_scope_display(
            "gmail",
            ["https://www.googleapis.com/auth/gmail.readonly"],
        )
        assert "read-only" in text.lower()
        assert "Billhound" in text

    def test_outlook_scope_display(self) -> None:
        text = format_scope_display(
            "outlook",
            ["https://graph.microsoft.com/Mail.Read"],
        )
        assert "read-only" in text.lower()

    def test_unknown_scope(self) -> None:
        text = format_scope_display("gmail", ["some.unknown.scope"])
        assert "Unknown scope" in text
