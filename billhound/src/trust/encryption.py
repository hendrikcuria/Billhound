"""
AES-256-GCM encryption utility for storing sensitive data at rest.
Used for: OAuth tokens, PDF password patterns.

Nonce (12 bytes) is prepended to ciphertext before base64 encoding.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionService:
    """AES-256-GCM encrypt/decrypt. Nonce is prepended to ciphertext."""

    NONCE_SIZE = 12  # 96-bit nonce for GCM

    def __init__(self, key_hex: str) -> None:
        self._key = bytes.fromhex(key_hex)
        if len(self._key) != 32:
            raise ValueError("Encryption key must be 32 bytes (64 hex characters)")
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string. Returns base64-encoded nonce+ciphertext."""
        nonce = os.urandom(self.NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Decrypt base64-encoded nonce+ciphertext. Returns plaintext string."""
        raw = base64.b64decode(token)
        nonce = raw[: self.NONCE_SIZE]
        ciphertext = raw[self.NONCE_SIZE :]
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
