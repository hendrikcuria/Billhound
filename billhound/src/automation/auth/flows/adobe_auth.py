"""Adobe authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

ADOBE_LOGIN_URL = "https://auth.services.adobe.com/"


@auth_register("adobe")
class AdobeAuthStrategy(BaseAuthStrategy):
    """
    Automates Adobe email/password login.

    Adobe uses a two-step login: email first, then password.

    Flow:
    1. Navigate to login page.
    2. Fill "Email address" field (get_by_label).
    3. Click "Continue" (get_by_role).
    4. Fill "Password" field (get_by_label).
    5. Click "Continue" (get_by_role).
    6. Wait for redirect to account page.
    """

    @property
    def name(self) -> str:
        return "adobe"

    @property
    def login_url(self) -> str:
        return ADOBE_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.adobe.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Step 1: Fill email
        email_field = page.get_by_label("Email address")
        await email_field.fill(credential.username)

        # Step 2: Click continue (email step)
        continue_btn = page.get_by_role("button", name="Continue")
        await continue_btn.click()

        logger.info("auth.adobe.email_submitted")

        # Step 3: Fill password
        password_field = page.get_by_label("Password")
        await password_field.wait_for(state="visible")
        await password_field.fill(credential.password)

        # Step 4: Click continue (password step)
        continue_btn = page.get_by_role("button", name="Continue")
        await continue_btn.click()

        # Wait for navigation to account area
        await page.wait_for_url("**/plans**", timeout=15_000)

        logger.info("auth.adobe.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
