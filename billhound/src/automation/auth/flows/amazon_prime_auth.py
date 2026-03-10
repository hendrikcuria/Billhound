"""Amazon Prime authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

AMAZON_LOGIN_URL = "https://www.amazon.com/ap/signin"


@auth_register("amazon prime")
class AmazonPrimeAuthStrategy(BaseAuthStrategy):
    """
    Automates Amazon email/password login.

    Amazon uses a two-step login: email first, then password.

    Flow:
    1. Navigate to sign-in page.
    2. Fill "Email or mobile phone number" (get_by_label).
    3. Click "Continue" (get_by_role).
    4. Fill "Password" field (get_by_label).
    5. Click "Sign-In" (get_by_role).
    6. Wait for redirect to account area.
    """

    @property
    def name(self) -> str:
        return "amazon prime"

    @property
    def login_url(self) -> str:
        return AMAZON_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.amazon_prime.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Step 1: Fill email
        email_field = page.get_by_label("Email or mobile phone number")
        await email_field.fill(credential.username)

        # Step 2: Click continue
        continue_btn = page.get_by_role("button", name="Continue")
        await continue_btn.click()

        logger.info("auth.amazon_prime.email_submitted")

        # Step 3: Fill password
        password_field = page.get_by_label("Password")
        await password_field.wait_for(state="visible")
        await password_field.fill(credential.password)

        # Step 4: Click sign-in
        signin_btn = page.get_by_role("button", name="Sign-In")
        await signin_btn.click()

        # Wait for navigation to account/pipeline area
        await page.wait_for_url("**/mc/**", timeout=15_000)

        logger.info("auth.amazon_prime.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
