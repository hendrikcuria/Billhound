"""YouTube Premium (Google) authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

GOOGLE_LOGIN_URL = "https://accounts.google.com/signin"


@auth_register("youtube premium")
class YoutubePremiumAuthStrategy(BaseAuthStrategy):
    """
    Automates Google account login for YouTube Premium.

    Google uses a two-step login: email first, then password.

    Flow:
    1. Navigate to Google sign-in.
    2. Fill "Email or phone" field (get_by_label).
    3. Click "Next" (get_by_role).
    4. Fill "Enter your password" field (get_by_label).
    5. Click "Next" (get_by_role).
    6. Wait for redirect to YouTube.
    """

    @property
    def name(self) -> str:
        return "youtube premium"

    @property
    def login_url(self) -> str:
        return GOOGLE_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.youtube_premium.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Step 1: Fill email
        email_field = page.get_by_label("Email or phone")
        await email_field.fill(credential.username)

        # Step 2: Click next
        next_btn = page.get_by_role("button", name="Next")
        await next_btn.click()

        logger.info("auth.youtube_premium.email_submitted")

        # Step 3: Fill password
        password_field = page.get_by_label("Enter your password")
        await password_field.wait_for(state="visible")
        await password_field.fill(credential.password)

        # Step 4: Click next
        next_btn = page.get_by_role("button", name="Next")
        await next_btn.click()

        # Wait for navigation to YouTube
        await page.wait_for_url("**/paid_memberships**", timeout=15_000)

        logger.info("auth.youtube_premium.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
