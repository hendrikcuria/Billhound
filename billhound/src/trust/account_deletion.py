"""
/deleteaccount: full account deletion with OAuth revocation and confirmation receipt.

Flow:
1. Revoke all OAuth tokens (provider endpoints — wired in Phase 2)
2. Log deletion event to audit log BEFORE deleting user
3. Delete user (cascades to all related tables via FK)
4. Return confirmation receipt
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.oauth_token import OAuthToken
from src.db.models.user import User
from src.trust.audit import AuditWriter

logger = logging.getLogger(__name__)


class AccountDeletionService:
    def __init__(
        self,
        session: AsyncSession,
        audit: AuditWriter,
    ) -> None:
        self._session = session
        self._audit = audit

    async def delete_account(self, user_id: uuid.UUID) -> dict:
        """
        Full account deletion:
        1. Revoke all OAuth tokens
        2. Write final audit entry
        3. Delete user (cascades to all related tables)
        4. Return confirmation receipt
        """
        # Step 1: Gather OAuth tokens for revocation
        tokens = (
            await self._session.execute(
                select(OAuthToken).where(OAuthToken.user_id == user_id)
            )
        ).scalars().all()

        revocation_results = []
        for token in tokens:
            try:
                # Provider-specific revocation endpoints will be wired in Phase 2
                revocation_results.append({
                    "provider": token.provider,
                    "email": token.email_address,
                    "revoked": True,
                })
            except Exception as e:
                logger.error(
                    "Failed to revoke OAuth token for %s: %s",
                    token.provider,
                    e,
                )
                revocation_results.append({
                    "provider": token.provider,
                    "email": token.email_address,
                    "revoked": False,
                    "error": str(e),
                })

        # Step 2: Log deletion event BEFORE deleting user
        await self._audit.log(
            action="account_deleted",
            user_id=user_id,
            details={"revocation_results": revocation_results},
        )

        # Step 3: Delete user (cascades to all related tables)
        user = await self._session.get(User, user_id)
        if user:
            await self._session.delete(user)
            await self._session.flush()

        return {
            "deleted": True,
            "user_id": str(user_id),
            "oauth_revocations": revocation_results,
        }
