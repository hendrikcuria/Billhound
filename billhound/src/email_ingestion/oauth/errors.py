"""OAuth error types."""
from __future__ import annotations


class OAuthError(Exception):
    """Raised when an OAuth flow fails."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"OAuth error ({provider}): {message}")
