"""Data types for the authentication subsystem."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthStatus(str, Enum):
    SUCCESS = "auth_success"
    FAILED = "auth_failed"
    CREDENTIALS_INVALID = "credentials_invalid"
    MFA_REQUIRED = "mfa_required"
    CAPTCHA_BLOCKED = "captcha_blocked"
    TIMEOUT = "auth_timeout"


@dataclass(frozen=True, slots=True)
class AuthResult:
    """Immutable outcome of an authentication strategy execution."""

    success: bool
    status: AuthStatus
    error_message: str | None = None
