"""NordVPN authentication flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.auth.auth_registry import auth_register
from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus

logger = structlog.get_logger()

NORDVPN_LOGIN_URL = "https://my.nordaccount.com/login/"


@auth_register("nordvpn")
class NordvpnAuthStrategy(BaseAuthStrategy):
    """
    Automates NordVPN account login.

    Flow:
    1. Navigate to login page.
    2. Fill "Email address" field (get_by_label).
    3. Fill "Password" field (get_by_label).
    4. Click "Log in" button (get_by_role).
    5. Wait for redirect to dashboard.
    """

    @property
    def name(self) -> str:
        return "nordvpn"

    @property
    def login_url(self) -> str:
        return NORDVPN_LOGIN_URL

    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        logger.info("auth.nordvpn.start")
        await page.goto(self.login_url, wait_until="networkidle")

        # Fill email
        email_field = page.get_by_label("Email address")
        await email_field.fill(credential.username)

        # Fill password
        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        # Click log in
        login_btn = page.get_by_role("button", name="Log in")
        await login_btn.click()

        # Wait for navigation to dashboard
        await page.wait_for_url("**/dashboard/**", timeout=15_000)

        logger.info("auth.nordvpn.success")
        return AuthResult(
            success=True,
            status=AuthStatus.SUCCESS,
        )
