from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.oauth_token import OAuthToken
from src.db.repositories.base import BaseRepository
from src.trust.encryption import EncryptionService


class OAuthTokenRepository(BaseRepository[OAuthToken]):
    """
    Encryption-enforced repository for OAuth tokens.
    Tokens are encrypted before storage; decrypted only at API call time.
    """

    def __init__(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        super().__init__(session, OAuthToken)
        self._encryption = encryption

    async def store_token(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime,
        scopes_granted: str,
        email_address: str,
    ) -> OAuthToken:
        """Store OAuth tokens, encrypting both tokens before hitting the DB."""
        return await self.create(
            user_id=user_id,
            provider=provider,
            access_token_encrypted=self._encryption.encrypt(access_token),
            refresh_token_encrypted=self._encryption.encrypt(refresh_token),
            token_expiry=token_expiry,
            scopes_granted=scopes_granted,
            email_address=email_address,
        )

    def decrypt_access_token(self, token: OAuthToken) -> str:
        """Decrypt access token. Use at moment of API call only."""
        return self._encryption.decrypt(token.access_token_encrypted)

    def decrypt_refresh_token(self, token: OAuthToken) -> str:
        """Decrypt refresh token. Use at moment of token refresh only."""
        return self._encryption.decrypt(token.refresh_token_encrypted)

    async def rotate_tokens(
        self,
        token: OAuthToken,
        *,
        new_access_token: str,
        new_refresh_token: str,
        new_expiry: datetime,
    ) -> OAuthToken:
        """Rotate tokens after refresh — encrypts new values before storage."""
        return await self.update(
            token,
            access_token_encrypted=self._encryption.encrypt(new_access_token),
            refresh_token_encrypted=self._encryption.encrypt(new_refresh_token),
            token_expiry=new_expiry,
        )

    async def get_by_user(self, user_id: uuid.UUID) -> Sequence[OAuthToken]:
        stmt = select(OAuthToken).where(OAuthToken.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_provider(
        self, user_id: uuid.UUID, provider: str
    ) -> OAuthToken | None:
        stmt = select(OAuthToken).where(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == provider,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
