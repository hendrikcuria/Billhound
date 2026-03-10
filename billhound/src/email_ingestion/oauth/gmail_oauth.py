"""
Gmail OAuth 2.0 flow using raw aiohttp.
No Google SDK dependency — just REST calls.
"""
from __future__ import annotations

import hashlib
import hmac
import base64
from urllib.parse import urlencode

import aiohttp
import structlog

from src.email_ingestion.oauth.errors import OAuthError

logger = structlog.get_logger()


class GmailOAuthClient:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        signing_key: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._signing_key = signing_key

    def get_authorization_url(self, user_id: str) -> str:
        """Build URL to redirect user to Google consent screen."""
        state = self._sign_state(user_id)
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access + refresh tokens."""
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self._redirect_uri,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.TOKEN_URL, data=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise OAuthError(
                        "gmail",
                        data.get("error_description", data.get("error", "Unknown")),
                    )
                return data

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Use refresh_token to get a new access_token."""
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.TOKEN_URL, data=payload) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise OAuthError(
                        "gmail",
                        data.get("error_description", data.get("error", "Unknown")),
                    )
                return data

    def _sign_state(self, user_id: str) -> str:
        """HMAC-sign user_id to prevent CSRF."""
        sig = hmac.new(
            self._signing_key.encode(), user_id.encode(), hashlib.sha256
        ).hexdigest()[:16]
        raw = f"{user_id}|{sig}"
        return base64.urlsafe_b64encode(raw.encode()).decode()

    def verify_state(self, state: str) -> str | None:
        """Verify HMAC-signed state. Returns user_id or None."""
        try:
            raw = base64.urlsafe_b64decode(state.encode()).decode()
            user_id, sig = raw.rsplit("|", 1)
            expected = hmac.new(
                self._signing_key.encode(), user_id.encode(), hashlib.sha256
            ).hexdigest()[:16]
            if hmac.compare_digest(sig, expected):
                return user_id
            return None
        except Exception:
            return None
