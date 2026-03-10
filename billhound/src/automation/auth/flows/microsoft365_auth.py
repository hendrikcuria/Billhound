"""Microsoft 365 authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

MICROSOFT_LOGIN_URL = "https://login.microsoftonline.com/"


@auth_register("microsoft 365")
class Microsoft365AuthStrategy(BaseAuthStrategy):
    """
    Automates Microsoft account login for Microsoft 365.

    Microsoft uses a two-step login: email first, then password.

    Flow:
    1. Navigate to Microsoft login.
    2. Fill "Email, phone, or Skype" field (get_by_label).
    3. Click "Next" (get_by_role).
    4. Fill "Password" field (get_by_label).
    5. Click "Sign in" (get_by_role).
    6. Wait for redirect to services page.
    """

    @property
    def name(self) -> str:
        return "microsoft 365"

    @property
    def login_url(self) -> str:
        return MICROSOFT_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.microsoft365.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Step 1: Fill email
        email_field = page.get_by_label("Email, phone, or Skype")
        await email_field.fill(credential.username)

        # Step 2: Click next
        next_btn = page.get_by_role("button", name="Next")
        await next_btn.click()

        logger.info("auth.microsoft365.email_submitted")

        # Step 3: Fill password
        password_field = page.get_by_label("Password")
        await password_field.wait_for(state="visible")
        await password_field.fill(credential.password)

        # Step 4: Click sign in
        signin_btn = page.get_by_role("button", name="Sign in")
        await signin_btn.click()

        # Wait for navigation to services area
        await page.wait_for_url("**/services**", timeout=15_000)

        logger.info("auth.microsoft365.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
