"""
OAuth consent tracking.
Records when users grant/revoke OAuth access for compliance.
"""
from __future__ import annotations

import uuid

from src.trust.audit import AuditWriter


class ConsentTracker:
    def __init__(self, audit: AuditWriter) -> None:
        self._audit = audit

    async def record_grant(
        self,
        user_id: uuid.UUID,
        provider: str,
        scopes: list[str],
        email: str,
    ) -> None:
        await self._audit.log(
            action="oauth_granted",
            user_id=user_id,
            entity_type="oauth_token",
            details={
                "provider": provider,
                "scopes": scopes,
                "email": email,
            },
        )

    async def record_revocation(
        self,
        user_id: uuid.UUID,
        provider: str,
        email: str,
    ) -> None:
        await self._audit.log(
            action="oauth_revoked",
            user_id=user_id,
            entity_type="oauth_token",
            details={
                "provider": provider,
                "email": email,
            },
        )
