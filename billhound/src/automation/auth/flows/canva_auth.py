"""Canva authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

CANVA_LOGIN_URL = "https://www.canva.com/login"


@auth_register("canva")
class CanvaAuthStrategy(BaseAuthStrategy):
    """
    Automates Canva email/password login.

    Flow:
    1. Navigate to login page.
    2. Click "Continue with email" (get_by_role).
    3. Fill "Email" field (get_by_label).
    4. Fill "Password" field (get_by_label).
    5. Click "Log in" (get_by_role).
    6. Wait for redirect to settings area.
    """

    @property
    def name(self) -> str:
        return "canva"

    @property
    def login_url(self) -> str:
        return CANVA_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.canva.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Step 1: Click "Continue with email" to reveal form
        email_option = page.get_by_role("button", name="Continue with email")
        await email_option.wait_for(state="visible")
        await email_option.click()

        logger.info("auth.canva.email_option_clicked")

        # Step 2: Fill email
        email_field = page.get_by_label("Email")
        await email_field.wait_for(state="visible")
        await email_field.fill(credential.username)

        # Step 3: Fill password
        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        # Step 4: Click log in
        login_btn = page.get_by_role("button", name="Log in")
        await login_btn.click()

        # Wait for navigation to settings area
        await page.wait_for_url("**/settings/**", timeout=15_000)

        logger.info("auth.canva.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
