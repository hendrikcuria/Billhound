"""Netflix authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

NETFLIX_LOGIN_URL = "https://www.netflix.com/login"


@auth_register("netflix")
class NetflixAuthStrategy(BaseAuthStrategy):
    """
    Automates Netflix email/password login.

    Flow:
    1. Navigate to login page.
    2. Fill email field (get_by_label).
    3. Fill password field (get_by_label).
    4. Click "Sign In" button (get_by_role).
    5. Wait for redirect away from login page.
    """

    @property
    def name(self) -> str:
        return "netflix"

    @property
    def login_url(self) -> str:
        return NETFLIX_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.netflix.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Fill email
        email_field = page.get_by_label("Email or phone number")
        await email_field.fill(credential.username)

        # Fill password
        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        # Click sign in
        sign_in_btn = page.get_by_role("button", name="Sign In")
        await sign_in_btn.click()

        # Wait for navigation away from login page
        await page.wait_for_url("**/browse**", timeout=15_000)

        logger.info("auth.netflix.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
