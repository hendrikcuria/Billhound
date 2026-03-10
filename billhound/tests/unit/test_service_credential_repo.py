"""
Tests that ServiceCredentialRepository enforces AES-256-GCM encryption
and provides correct CRUD operations for service login credentials.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.service_credential_repo import ServiceCredentialRepository
from src.trust.encryption import EncryptionService
from tests.factories import make_user

# Deterministic test key (32 bytes = 64 hex chars)
TEST_KEY = "a" * 64


@pytest.fixture
def encryption() -> EncryptionService:
    return EncryptionService(TEST_KEY)


class TestServiceCredentialEncryption:
    @pytest.mark.asyncio
    async def test_store_encrypts_both_fields(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950001)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)
        cred = await repo.store_credential(
            user_id=user.id,
            service_name="netflix",
            username="user@example.com",
            password="s3cret!",
        )

        assert cred.username_encrypted != "user@example.com"
        assert cred.password_encrypted != "s3cret!"
        assert len(cred.username_encrypted) > 20
        assert len(cred.password_encrypted) > 20

    @pytest.mark.asyncio
    async def test_decrypt_roundtrip(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950002)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)
        cred = await repo.store_credential(
            user_id=user.id,
            service_name="spotify",
            username="listener@music.com",
            password="p@ssw0rd_123",
        )

        assert repo.decrypt_username(cred) == "listener@music.com"
        assert repo.decrypt_password(cred) == "p@ssw0rd_123"

    @pytest.mark.asyncio
    async def test_wrong_key_cannot_decrypt(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950003)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)
        cred = await repo.store_credential(
            user_id=user.id,
            service_name="netflix",
            username="user@test.com",
            password="secret",
        )

        wrong_encryption = EncryptionService("b" * 64)
        wrong_repo = ServiceCredentialRepository(session, wrong_encryption)

        with pytest.raises(Exception):
            wrong_repo.decrypt_password(cred)


class TestServiceCredentialCRUD:
    @pytest.mark.asyncio
    async def test_upsert_updates_existing(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950010)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)

        # First store
        cred1 = await repo.upsert_credential(
            user_id=user.id,
            service_name="netflix",
            username="old@example.com",
            password="old_pass",
        )

        # Upsert with new values
        cred2 = await repo.upsert_credential(
            user_id=user.id,
            service_name="netflix",
            username="new@example.com",
            password="new_pass",
        )

        # Same row updated, not duplicated
        assert cred1.id == cred2.id
        assert repo.decrypt_username(cred2) == "new@example.com"
        assert repo.decrypt_password(cred2) == "new_pass"

    @pytest.mark.asyncio
    async def test_get_by_user(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950011)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)
        await repo.store_credential(
            user_id=user.id, service_name="netflix",
            username="a@a.com", password="p1",
        )
        await repo.store_credential(
            user_id=user.id, service_name="spotify",
            username="b@b.com", password="p2",
        )

        creds = await repo.get_by_user(user.id)
        assert len(creds) == 2
        names = {c.service_name for c in creds}
        assert names == {"netflix", "spotify"}

    @pytest.mark.asyncio
    async def test_delete_by_service(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950012)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)
        await repo.store_credential(
            user_id=user.id, service_name="netflix",
            username="u@u.com", password="p",
        )

        assert await repo.delete_by_service(user.id, "netflix") is True
        assert await repo.delete_by_service(user.id, "netflix") is False
        assert await repo.get_by_service(user.id, "netflix") is None

    @pytest.mark.asyncio
    async def test_service_name_normalized(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=950013)
        session.add(user)
        await session.flush()

        repo = ServiceCredentialRepository(session, encryption)
        await repo.store_credential(
            user_id=user.id, service_name="  Netflix  ",
            username="u@u.com", password="p",
        )

        # Lookup with different casing/whitespace resolves to same record
        cred = await repo.get_by_service(user.id, "netflix")
        assert cred is not None
        cred2 = await repo.get_by_service(user.id, "  NETFLIX  ")
        assert cred2 is not None
        assert cred.id == cred2.id
