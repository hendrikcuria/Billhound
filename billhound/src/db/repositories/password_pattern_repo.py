from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.password_pattern import PasswordPattern
from src.db.repositories.base import BaseRepository
from src.trust.encryption import EncryptionService


class PasswordPatternRepository(BaseRepository[PasswordPattern]):
    """
    Encryption-enforced repository for PDF password patterns.
    All writes encrypt via AES-256-GCM; plaintext never reaches the DB.
    """

    def __init__(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        super().__init__(session, PasswordPattern)
        self._encryption = encryption

    async def create_pattern(
        self,
        *,
        user_id: uuid.UUID,
        bank_name: str,
        pattern_description: str,
        password_plaintext: str,
        sender_email_pattern: str | None = None,
    ) -> PasswordPattern:
        """Create a password pattern, encrypting the password before storage."""
        encrypted = self._encryption.encrypt(password_plaintext)
        return await self.create(
            user_id=user_id,
            bank_name=bank_name,
            pattern_description=pattern_description,
            password_encrypted=encrypted,
            sender_email_pattern=sender_email_pattern,
        )

    def decrypt_password(self, pattern: PasswordPattern) -> str:
        """Decrypt a stored password. Use at moment of PDF unlock only."""
        return self._encryption.decrypt(pattern.password_encrypted)

    async def get_by_user(self, user_id: uuid.UUID) -> Sequence[PasswordPattern]:
        stmt = select(PasswordPattern).where(PasswordPattern.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_sender(
        self, user_id: uuid.UUID, sender_email: str
    ) -> PasswordPattern | None:
        stmt = select(PasswordPattern).where(
            PasswordPattern.user_id == user_id,
            PasswordPattern.sender_email_pattern == sender_email,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
