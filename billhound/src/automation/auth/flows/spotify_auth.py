"""Spotify authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

SPOTIFY_LOGIN_URL = "https://accounts.spotify.com/login"


@auth_register("spotify")
class SpotifyAuthStrategy(BaseAuthStrategy):
    """
    Automates Spotify email/password login.

    Flow:
    1. Navigate to login page.
    2. Fill "Email or username" field (get_by_label).
    3. Fill "Password" field (get_by_label).
    4. Click "Log In" button (get_by_role).
    5. Wait for redirect to account page.
    """

    @property
    def name(self) -> str:
        return "spotify"

    @property
    def login_url(self) -> str:
        return SPOTIFY_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.spotify.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Fill email/username
        email_field = page.get_by_label("Email or username")
        await email_field.fill(credential.username)

        # Fill password
        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        # Click log in
        login_btn = page.get_by_role("button", name="Log In")
        await login_btn.click()

        # Wait for navigation to account area
        await page.wait_for_url("**/account/**", timeout=15_000)

        logger.info("auth.spotify.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
