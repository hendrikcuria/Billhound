"""
Unit tests for AES-256-GCM encryption service.
"""
from __future__ import annotations

import secrets

import pytest

from src.trust.encryption import EncryptionService


@pytest.fixture
def encryption_key() -> str:
    return secrets.token_hex(32)


@pytest.fixture
def svc(encryption_key: str) -> EncryptionService:
    return EncryptionService(encryption_key)


class TestEncryptionService:
    def test_roundtrip(self, svc: EncryptionService) -> None:
        plaintext = "my-secret-password-123"
        encrypted = svc.encrypt(plaintext)
        assert encrypted != plaintext
        assert svc.decrypt(encrypted) == plaintext

    def test_roundtrip_unicode(self, svc: EncryptionService) -> None:
        plaintext = "password-with-unicode-\u00e9\u00e8\u00ea"
        encrypted = svc.encrypt(plaintext)
        assert svc.decrypt(encrypted) == plaintext

    def test_roundtrip_empty_string(self, svc: EncryptionService) -> None:
        encrypted = svc.encrypt("")
        assert svc.decrypt(encrypted) == ""

    def test_roundtrip_long_string(self, svc: EncryptionService) -> None:
        plaintext = "x" * 10000
        encrypted = svc.encrypt(plaintext)
        assert svc.decrypt(encrypted) == plaintext

    def test_different_nonce_each_time(self, svc: EncryptionService) -> None:
        plaintext = "same-input"
        enc1 = svc.encrypt(plaintext)
        enc2 = svc.encrypt(plaintext)
        assert enc1 != enc2  # Different nonce each time
        assert svc.decrypt(enc1) == plaintext
        assert svc.decrypt(enc2) == plaintext

    def test_wrong_key_fails(self, encryption_key: str) -> None:
        svc1 = EncryptionService(encryption_key)
        svc2 = EncryptionService(secrets.token_hex(32))
        encrypted = svc1.encrypt("secret")
        with pytest.raises(Exception):
            svc2.decrypt(encrypted)

    def test_tampered_ciphertext_fails(self, svc: EncryptionService) -> None:
        encrypted = svc.encrypt("secret")
        # Flip a byte in the middle
        import base64
        raw = bytearray(base64.b64decode(encrypted))
        raw[len(raw) // 2] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(Exception):
            svc.decrypt(tampered)

    def test_invalid_key_length(self) -> None:
        with pytest.raises(ValueError, match="32 bytes"):
            EncryptionService("aabbccdd")  # Too short

    def test_invalid_key_hex(self) -> None:
        with pytest.raises(ValueError):
            EncryptionService("zz" * 32)  # Invalid hex
