"""Encryption-enforced repository for service credentials."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.service_credential import ServiceCredential
from src.db.repositories.base import BaseRepository
from src.trust.encryption import EncryptionService


class ServiceCredentialRepository(BaseRepository[ServiceCredential]):
    """
    Encryption-enforced repository for service login credentials.
    All writes encrypt via AES-256-GCM; plaintext never reaches the DB.
    """

    def __init__(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        super().__init__(session, ServiceCredential)
        self._encryption = encryption

    async def store_credential(
        self,
        *,
        user_id: uuid.UUID,
        service_name: str,
        username: str,
        password: str,
        auth_method: str = "credential",
    ) -> ServiceCredential:
        """Store a credential, encrypting both username and password."""
        return await self.create(
            user_id=user_id,
            service_name=service_name.lower().strip(),
            username_encrypted=self._encryption.encrypt(username),
            password_encrypted=self._encryption.encrypt(password),
            auth_method=auth_method,
        )

    async def upsert_credential(
        self,
        *,
        user_id: uuid.UUID,
        service_name: str,
        username: str,
        password: str,
    ) -> ServiceCredential:
        """Create or update credential for a service."""
        existing = await self.get_by_service(user_id, service_name)
        if existing:
            return await self.update(
                existing,
                username_encrypted=self._encryption.encrypt(username),
                password_encrypted=self._encryption.encrypt(password),
            )
        return await self.store_credential(
            user_id=user_id,
            service_name=service_name,
            username=username,
            password=password,
        )

    def decrypt_username(self, credential: ServiceCredential) -> str:
        """Decrypt a stored username. Use at moment of login only."""
        return self._encryption.decrypt(credential.username_encrypted)

    def decrypt_password(self, credential: ServiceCredential) -> str:
        """Decrypt a stored password. Use at moment of login only."""
        return self._encryption.decrypt(credential.password_encrypted)

    async def get_by_user(
        self, user_id: uuid.UUID
    ) -> Sequence[ServiceCredential]:
        stmt = select(ServiceCredential).where(
            ServiceCredential.user_id == user_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_service(
        self, user_id: uuid.UUID, service_name: str
    ) -> ServiceCredential | None:
        stmt = select(ServiceCredential).where(
            ServiceCredential.user_id == user_id,
            ServiceCredential.service_name == service_name.lower().strip(),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_service(
        self, user_id: uuid.UUID, service_name: str
    ) -> bool:
        """Delete credential for a service. Returns True if found and deleted."""
        credential = await self.get_by_service(user_id, service_name)
        if credential:
            await self.delete(credential)
            return True
        return False
