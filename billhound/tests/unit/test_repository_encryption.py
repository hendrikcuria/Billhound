"""
Tests that AES-256-GCM encryption is enforced at the repository layer.
Plaintext secrets must never reach the database.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.trust.encryption import EncryptionService
from src.db.repositories.password_pattern_repo import PasswordPatternRepository
from src.db.repositories.oauth_token_repo import OAuthTokenRepository
from tests.factories import make_user

# Deterministic test key (32 bytes = 64 hex chars)
TEST_KEY = "a" * 64


@pytest.fixture
def encryption() -> EncryptionService:
    return EncryptionService(TEST_KEY)


class TestPasswordPatternEncryption:
    @pytest.mark.asyncio
    async def test_create_pattern_encrypts_password(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=900001)
        session.add(user)
        await session.flush()

        repo = PasswordPatternRepository(session, encryption)
        pattern = await repo.create_pattern(
            user_id=user.id,
            bank_name="Maybank",
            pattern_description="Last 4 digits of IC",
            password_plaintext="1234",
            sender_email_pattern="statement@maybank.com",
        )

        # The stored value must NOT be the plaintext
        assert pattern.password_encrypted != "1234"
        # It must be a valid base64 string (AES-256-GCM output)
        assert len(pattern.password_encrypted) > 20

    @pytest.mark.asyncio
    async def test_decrypt_password_roundtrip(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=900002)
        session.add(user)
        await session.flush()

        repo = PasswordPatternRepository(session, encryption)
        pattern = await repo.create_pattern(
            user_id=user.id,
            bank_name="CIMB",
            pattern_description="NRIC last 6",
            password_plaintext="secret_password_123",
        )

        # Decrypt must return the original plaintext
        decrypted = repo.decrypt_password(pattern)
        assert decrypted == "secret_password_123"

    @pytest.mark.asyncio
    async def test_wrong_key_cannot_decrypt(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=900003)
        session.add(user)
        await session.flush()

        repo = PasswordPatternRepository(session, encryption)
        pattern = await repo.create_pattern(
            user_id=user.id,
            bank_name="RHB",
            pattern_description="DOB DDMMYYYY",
            password_plaintext="01011990",
        )

        # A different key must fail to decrypt
        wrong_key = "b" * 64
        wrong_encryption = EncryptionService(wrong_key)
        wrong_repo = PasswordPatternRepository(session, wrong_encryption)

        with pytest.raises(Exception):
            wrong_repo.decrypt_password(pattern)


class TestOAuthTokenEncryption:
    @pytest.mark.asyncio
    async def test_store_token_encrypts_both_tokens(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=900010)
        session.add(user)
        await session.flush()

        repo = OAuthTokenRepository(session, encryption)
        token = await repo.store_token(
            user_id=user.id,
            provider="gmail",
            access_token="ya29.access_token_plaintext",
            refresh_token="1//refresh_token_plaintext",
            token_expiry=datetime(2026, 6, 1, tzinfo=timezone.utc),
            scopes_granted="https://www.googleapis.com/auth/gmail.readonly",
            email_address="user@gmail.com",
        )

        # Neither stored value should be plaintext
        assert token.access_token_encrypted != "ya29.access_token_plaintext"
        assert token.refresh_token_encrypted != "1//refresh_token_plaintext"

    @pytest.mark.asyncio
    async def test_decrypt_tokens_roundtrip(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=900011)
        session.add(user)
        await session.flush()

        repo = OAuthTokenRepository(session, encryption)
        token = await repo.store_token(
            user_id=user.id,
            provider="outlook",
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9",
            refresh_token="M.R3_BAY.refresh_outlook",
            token_expiry=datetime(2026, 6, 1, tzinfo=timezone.utc),
            scopes_granted="https://graph.microsoft.com/Mail.Read",
            email_address="user@outlook.com",
        )

        assert repo.decrypt_access_token(token) == "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9"
        assert repo.decrypt_refresh_token(token) == "M.R3_BAY.refresh_outlook"

    @pytest.mark.asyncio
    async def test_rotate_tokens_re_encrypts(
        self, session: AsyncSession, encryption: EncryptionService
    ) -> None:
        user = make_user(telegram_id=900012)
        session.add(user)
        await session.flush()

        repo = OAuthTokenRepository(session, encryption)
        token = await repo.store_token(
            user_id=user.id,
            provider="gmail",
            access_token="old_access",
            refresh_token="old_refresh",
            token_expiry=datetime(2026, 6, 1, tzinfo=timezone.utc),
            scopes_granted="https://www.googleapis.com/auth/gmail.readonly",
            email_address="user@gmail.com",
        )

        old_encrypted_access = token.access_token_encrypted

        # Rotate
        new_expiry = datetime(2026, 7, 1, tzinfo=timezone.utc)
        rotated = await repo.rotate_tokens(
            token,
            new_access_token="new_access_v2",
            new_refresh_token="new_refresh_v2",
            new_expiry=new_expiry,
        )

        # New encrypted value must differ from old
        assert rotated.access_token_encrypted != old_encrypted_access
        # Decrypts to the new plaintext
        assert repo.decrypt_access_token(rotated) == "new_access_v2"
        assert repo.decrypt_refresh_token(rotated) == "new_refresh_v2"
        assert rotated.token_expiry == new_expiry
