"""Tests for OAuth clients — URL generation, state HMAC signing/verification."""
from __future__ import annotations

from src.email_ingestion.oauth.gmail_oauth import GmailOAuthClient
from src.email_ingestion.oauth.outlook_oauth import OutlookOAuthClient


SIGNING_KEY = "test_signing_key_for_hmac"


class TestGmailOAuth:
    def setup_method(self) -> None:
        self.client = GmailOAuthClient(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:8080/oauth/gmail/callback",
            signing_key=SIGNING_KEY,
        )

    def test_authorization_url_contains_required_params(self) -> None:
        url = self.client.get_authorization_url("user-123")
        assert "accounts.google.com" in url
        assert "client_id=test-client-id" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert "scope=" in url
        assert "gmail.readonly" in url
        assert "access_type=offline" in url
        assert "state=" in url

    def test_state_signing_roundtrip(self) -> None:
        state = self.client._sign_state("user-456")
        result = self.client.verify_state(state)
        assert result == "user-456"

    def test_state_verification_fails_with_wrong_key(self) -> None:
        state = self.client._sign_state("user-789")
        other_client = GmailOAuthClient(
            client_id="x",
            client_secret="x",
            redirect_uri="x",
            signing_key="different_key",
        )
        assert other_client.verify_state(state) is None

    def test_state_verification_fails_with_tampered_state(self) -> None:
        assert self.client.verify_state("invalid_base64_state") is None

    def test_state_contains_user_id(self) -> None:
        import base64

        state = self.client._sign_state("my-user-id")
        decoded = base64.urlsafe_b64decode(state).decode()
        assert "my-user-id" in decoded


class TestOutlookOAuth:
    def setup_method(self) -> None:
        self.client = OutlookOAuthClient(
            client_id="test-outlook-id",
            client_secret="test-outlook-secret",
            redirect_uri="http://localhost:8080/oauth/outlook/callback",
            signing_key=SIGNING_KEY,
        )

    def test_authorization_url_contains_required_params(self) -> None:
        url = self.client.get_authorization_url("user-abc")
        assert "login.microsoftonline.com" in url
        assert "client_id=test-outlook-id" in url
        assert "response_type=code" in url
        assert "Mail.Read" in url
        assert "offline_access" in url
        assert "state=" in url

    def test_state_signing_roundtrip(self) -> None:
        state = self.client._sign_state("user-xyz")
        result = self.client.verify_state(state)
        assert result == "user-xyz"

    def test_uuid_in_state(self) -> None:
        import uuid

        uid = str(uuid.uuid4())
        state = self.client._sign_state(uid)
        assert self.client.verify_state(state) == uid
