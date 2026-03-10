"""
Tests that deleting a User cascades hard deletes across all related tables,
as mandated by the PRD kill switch (/deleteaccount).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog
from src.db.models.cancellation_log import CancellationLog
from src.db.models.oauth_token import OAuthToken
from src.db.models.password_pattern import PasswordPattern
from src.db.models.subscription import Subscription
from src.db.models.user import User
from src.trust.audit import AuditWriter
from src.trust.privacy_manager import PrivacyManager
from tests.factories import (
    make_cancellation_log,
    make_oauth_token,
    make_password_pattern,
    make_subscription,
    make_user,
)


class TestCascadingHardDeletes:
    @pytest.mark.asyncio
    async def test_delete_user_cascades_all_children(
        self, session: AsyncSession
    ) -> None:
        """Deleting a user must hard-delete subscriptions, tokens, patterns, and logs."""
        user = make_user(telegram_id=800001)
        session.add(user)
        await session.flush()
        user_id = user.id

        # Create related records across all child tables
        session.add(make_subscription(user_id, service_name="Netflix"))
        session.add(make_subscription(user_id, service_name="Spotify"))
        session.add(make_oauth_token(user_id, provider="gmail"))
        session.add(make_password_pattern(user_id, bank_name="Maybank"))
        session.add(make_cancellation_log(user_id, service_name="Adobe"))
        await session.flush()

        # Verify everything exists
        assert len((await session.execute(select(Subscription).where(Subscription.user_id == user_id))).scalars().all()) == 2
        assert len((await session.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))).scalars().all()) == 1
        assert len((await session.execute(select(PasswordPattern).where(PasswordPattern.user_id == user_id))).scalars().all()) == 1
        assert len((await session.execute(select(CancellationLog).where(CancellationLog.user_id == user_id))).scalars().all()) == 1

        # Delete user
        await session.delete(user)
        await session.flush()

        # All children must be gone — hard deletes, not soft
        assert (await session.get(User, user_id)) is None
        assert len((await session.execute(select(Subscription).where(Subscription.user_id == user_id))).scalars().all()) == 0
        assert len((await session.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))).scalars().all()) == 0
        assert len((await session.execute(select(PasswordPattern).where(PasswordPattern.user_id == user_id))).scalars().all()) == 0
        assert len((await session.execute(select(CancellationLog).where(CancellationLog.user_id == user_id))).scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_audit_log_preserved_after_user_deletion(
        self, session: AsyncSession
    ) -> None:
        """Audit log entries must survive user deletion (SET NULL on user_id)."""
        user = make_user(telegram_id=800002)
        session.add(user)
        await session.flush()
        user_id = user.id

        # Create an audit entry for this user
        writer = AuditWriter(session)
        await writer.log(action="some_action", user_id=user_id)

        # Delete user
        await session.delete(user)
        await session.flush()

        # Expire cached objects so SQLAlchemy re-reads SET NULL from DB
        session.expire_all()

        # Audit entry must still exist, with user_id set to NULL
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "some_action")
        )
        entry = result.scalar_one()
        assert entry is not None
        assert entry.user_id is None  # SET NULL, not deleted

    @pytest.mark.asyncio
    async def test_delete_account_full_flow(
        self, session: AsyncSession
    ) -> None:
        """PrivacyManager.delete_account() must cascade and preserve audit trail."""
        user = make_user(telegram_id=800003)
        session.add(user)
        await session.flush()
        user_id = user.id

        session.add(make_subscription(user_id))
        session.add(make_oauth_token(user_id))
        session.add(make_password_pattern(user_id))
        await session.flush()

        pm = PrivacyManager(session)
        result = await pm.delete_account(user_id)

        assert result["deleted"] is True
        assert result["user_id"] == str(user_id)

        # Expire cached objects so SQLAlchemy re-reads SET NULL from DB
        session.expire_all()

        # User gone
        assert (await session.get(User, user_id)) is None

        # Children gone
        assert len((await session.execute(select(Subscription).where(Subscription.user_id == user_id))).scalars().all()) == 0
        assert len((await session.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))).scalars().all()) == 0
        assert len((await session.execute(select(PasswordPattern).where(PasswordPattern.user_id == user_id))).scalars().all()) == 0

        # Audit trail preserved
        audit_result = await session.execute(
            select(AuditLog).where(AuditLog.action == "account_deleted")
        )
        audit_entry = audit_result.scalar_one()
        assert audit_entry is not None
        assert audit_entry.user_id is None  # SET NULL after cascade
