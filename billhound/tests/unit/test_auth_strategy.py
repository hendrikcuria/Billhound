"""
Tests for the Playwright authentication strategy subsystem.

Uses aiohttp to serve mock HTML login pages and real Playwright to test
the login flow and graceful fallback — no production servers.
"""
from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import web

from src.automation.auth.base_auth_strategy import BaseAuthStrategy, DecryptedCredential
from src.automation.auth.models import AuthResult, AuthStatus
from src.automation.auth.auth_registry import (
    _AUTH_REGISTRY,
    get_auth_strategy,
    has_auth_strategy,
)
from src.automation.models import CancellationResult
from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.orchestrator import CancellationOrchestrator
from src.automation.registry import _REGISTRY
from src.config.constants import CancellationStatus

# ─── Mock HTML Pages ───────────────────────────────────────────────

HAPPY_LOGIN_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Sign In</title></head>
<body id="login-page">
  <form id="login-form">
    <label for="email">Email or phone number</label>
    <input id="email" name="email" type="text" />
    <label for="password">Password</label>
    <input id="password" name="password" type="password" />
    <button type="button" onclick="
      var e = document.getElementById('email').value;
      var p = document.getElementById('password').value;
      if (e && p) {
        document.getElementById('login-form').style.display='none';
        document.getElementById('browse').style.display='block';
        history.pushState({}, '', '/browse');
      }
    ">Sign In</button>
  </form>
  <div id="browse" style="display:none;">
    <h1>Welcome to StreamService</h1>
  </div>
</body>
</html>
"""

BAD_CREDS_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Sign In</title></head>
<body>
  <form id="login-form">
    <label for="email">Email or phone number</label>
    <input id="email" name="email" type="text" />
    <label for="password">Password</label>
    <input id="password" name="password" type="password" />
    <button type="button" onclick="
      document.getElementById('error-msg').style.display='block';
    ">Sign In</button>
  </form>
  <div id="error-msg" style="display:none;">
    <p>Invalid email or password</p>
  </div>
</body>
</html>
"""

TIMEOUT_LOGIN_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Sign In</title></head>
<body>
  <form>
    <label for="email">Email or phone number</label>
    <input id="email" name="email" type="text" />
    <label for="password">Password</label>
    <input id="password" name="password" type="password" />
    <button style="display:none;">Sign In</button>
  </form>
</body>
</html>
"""

# Happy cancel page (used after auth in integration test)
HAPPY_CANCEL_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Cancel Subscription</title></head>
<body>
  <h1>Manage Subscription</h1>
  <button onclick="
    document.getElementById('step2').style.display='block';
    this.style.display='none';
  ">Cancel Membership</button>
  <div id="step2" style="display:none;">
    <p>Are you sure?</p>
    <button onclick="
      document.getElementById('step3').style.display='block';
      document.getElementById('step2').style.display='none';
    ">Finish Cancellation</button>
  </div>
  <div id="step3" style="display:none;">
    <h2>Your membership has been cancelled</h2>
  </div>
</body>
</html>
"""


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def unused_tcp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def auth_mock_server_app():
    app = web.Application()

    async def login_handler(request: web.Request) -> web.Response:
        return web.Response(text=HAPPY_LOGIN_HTML, content_type="text/html")

    async def bad_creds_handler(request: web.Request) -> web.Response:
        return web.Response(text=BAD_CREDS_HTML, content_type="text/html")

    async def timeout_handler(request: web.Request) -> web.Response:
        return web.Response(text=TIMEOUT_LOGIN_HTML, content_type="text/html")

    async def cancel_handler(request: web.Request) -> web.Response:
        return web.Response(text=HAPPY_CANCEL_HTML, content_type="text/html")

    # Serve /browse after login redirect
    async def browse_handler(request: web.Request) -> web.Response:
        return web.Response(
            text="<html><body><h1>Welcome</h1></body></html>",
            content_type="text/html",
        )

    app.router.add_get("/login", login_handler)
    app.router.add_get("/bad-creds", bad_creds_handler)
    app.router.add_get("/timeout-login", timeout_handler)
    app.router.add_get("/cancel", cancel_handler)
    app.router.add_get("/browse", browse_handler)
    return app


@pytest.fixture
async def auth_mock_server(auth_mock_server_app, unused_tcp_port):
    runner = web.AppRunner(auth_mock_server_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    yield f"http://127.0.0.1:{unused_tcp_port}"
    await runner.cleanup()


# ─── Mock Strategies (test-only) ──────────────────────────────────

class MockLoginStrategy(BaseAuthStrategy):
    """Logs into the mock HTML login form."""

    def __init__(self, login_url: str | None = None) -> None:
        self._login_url = login_url

    @property
    def name(self) -> str:
        return "mock_login"

    @property
    def login_url(self) -> str | None:
        return self._login_url

    async def authenticate(self, page, credential):
        await page.goto(self._login_url, wait_until="networkidle")

        email_field = page.get_by_label("Email or phone number")
        await email_field.fill(credential.username)

        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        sign_in_btn = page.get_by_role("button", name="Sign In")
        await sign_in_btn.click()

        # Wait for redirect to /browse
        await page.wait_for_url("**/browse**", timeout=5000)

        return AuthResult(success=True, status=AuthStatus.SUCCESS)


class MockBadCredsStrategy(BaseAuthStrategy):
    """Submits to the bad-creds page, detects error."""

    def __init__(self, login_url: str | None = None) -> None:
        self._login_url = login_url

    @property
    def name(self) -> str:
        return "mock_bad_creds"

    async def authenticate(self, page, credential):
        await page.goto(self._login_url, wait_until="networkidle")

        email_field = page.get_by_label("Email or phone number")
        await email_field.fill(credential.username)

        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        sign_in_btn = page.get_by_role("button", name="Sign In")
        await sign_in_btn.click()

        # Check for error message instead of URL change
        error_msg = page.get_by_text("Invalid email or password")
        await error_msg.wait_for(state="visible", timeout=3000)

        return AuthResult(
            success=False,
            status=AuthStatus.CREDENTIALS_INVALID,
            error_message="Invalid email or password",
        )


class MockTimeoutAuthStrategy(BaseAuthStrategy):
    """Tries to click hidden Sign In button — will timeout."""

    def __init__(self, login_url: str | None = None) -> None:
        self._login_url = login_url

    @property
    def name(self) -> str:
        return "mock_timeout_auth"

    async def authenticate(self, page, credential):
        await page.goto(self._login_url, wait_until="networkidle")

        email_field = page.get_by_label("Email or phone number")
        await email_field.fill(credential.username)

        password_field = page.get_by_label("Password")
        await password_field.fill(credential.password)

        # Button is hidden — will timeout
        sign_in_btn = page.get_by_role("button", name="Sign In")
        await sign_in_btn.click(timeout=2000)

        return AuthResult(success=True, status=AuthStatus.SUCCESS)


class MockCancelStrategy(BaseCancellationStrategy):
    """Clicks through the cancel flow on the mock server."""

    def __init__(self, cancel_url: str | None = None) -> None:
        self._cancel_url = cancel_url

    @property
    def name(self) -> str:
        return "mock_auth_cancel"

    async def execute(self, page, subscription):
        url = self._cancel_url or subscription.cancellation_url
        await page.goto(url, wait_until="networkidle")

        cancel_btn = page.get_by_role("button", name="Cancel Membership")
        await cancel_btn.click()

        finish_btn = page.get_by_role("button", name="Finish Cancellation")
        await finish_btn.click()

        confirmation = page.get_by_text("cancelled", exact=False)
        await confirmation.wait_for(state="visible")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )


# ─── Mock Subscription ────────────────────────────────────────────

def _mock_subscription(
    service_name: str = "Netflix",
    cancellation_url: str | None = None,
) -> MagicMock:
    sub = MagicMock()
    sub.service_name = service_name
    sub.cancellation_url = cancellation_url
    sub.id = "test-sub-id"
    return sub


def _make_credential(
    username: str = "test@example.com",
    password: str = "testpass123",
    service_name: str = "mock_login",
) -> DecryptedCredential:
    return DecryptedCredential(
        username=username,
        password=password,
        service_name=service_name,
    )


# ─── Unit Tests (no Playwright) ───────────────────────────────────

class TestAuthResult:
    def test_success_result(self) -> None:
        result = AuthResult(success=True, status=AuthStatus.SUCCESS)
        assert result.success is True
        assert result.status == AuthStatus.SUCCESS
        assert result.error_message is None

    def test_failed_result(self) -> None:
        result = AuthResult(
            success=False,
            status=AuthStatus.CREDENTIALS_INVALID,
            error_message="Wrong password",
        )
        assert result.success is False
        assert result.status == AuthStatus.CREDENTIALS_INVALID
        assert result.error_message == "Wrong password"

    def test_frozen_immutable(self) -> None:
        result = AuthResult(success=True, status=AuthStatus.SUCCESS)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_all_statuses(self) -> None:
        statuses = [s for s in AuthStatus]
        assert len(statuses) == 6
        assert AuthStatus.MFA_REQUIRED in statuses
        assert AuthStatus.CAPTCHA_BLOCKED in statuses


class TestDecryptedCredential:
    def test_frozen(self) -> None:
        cred = DecryptedCredential(
            username="u", password="p", service_name="s"
        )
        with pytest.raises(AttributeError):
            cred.password = "new"  # type: ignore[misc]


class TestAuthRegistry:
    def test_netflix_registered(self) -> None:
        import src.automation.auth.flows  # noqa: F401

        assert has_auth_strategy("Netflix")
        assert has_auth_strategy("netflix")
        assert has_auth_strategy("  Netflix  ")

    def test_unknown_service(self) -> None:
        assert has_auth_strategy("SomeUnknownAuthService123") is False

    def test_get_auth_strategy_returns_instance(self) -> None:
        import src.automation.auth.flows  # noqa: F401

        strategy = get_auth_strategy("netflix")
        assert strategy is not None
        assert strategy.name == "netflix"

    def test_get_auth_strategy_unknown_returns_none(self) -> None:
        result = get_auth_strategy("nonexistent_auth_xyz")
        assert result is None


# ─── Integration Tests (real Playwright against mock server) ──────

@pytest.mark.asyncio
class TestAuthHappyPath:
    async def test_successful_login(self, auth_mock_server, tmp_path) -> None:
        """Auth strategy fills form, clicks Sign In, redirects to /browse."""
        from src.automation.auth.auth_registry import _AUTH_REGISTRY

        strategy = MockLoginStrategy(login_url=f"{auth_mock_server}/login")
        _AUTH_REGISTRY["mock_login"] = type(strategy)
        _REGISTRY["mock_login"] = MockCancelStrategy

        try:
            sub = _mock_subscription(
                service_name="mock_login",
                cancellation_url=f"{auth_mock_server}/cancel",
            )
            credential = _make_credential()

            orchestrator = CancellationOrchestrator(
                headless=True,
                timeout_ms=10_000,
                screenshot_dir=str(tmp_path),
            )

            # Patch the auth strategy to use the correct URL
            _AUTH_REGISTRY["mock_login"] = type(
                "PatchedMockLogin", (MockLoginStrategy,),
                {"__init__": lambda self: MockLoginStrategy.__init__(
                    self, f"{auth_mock_server}/login"
                )},
            )
            # Patch the cancel strategy to use correct URL
            _REGISTRY["mock_login"] = type(
                "PatchedMockCancel", (MockCancelStrategy,),
                {"__init__": lambda self: MockCancelStrategy.__init__(
                    self, f"{auth_mock_server}/cancel"
                )},
            )

            result = await orchestrator.cancel(sub, credential=credential)

            assert result.success is True
            assert result.status == CancellationStatus.SUCCESS
            assert result.screenshot_path is not None
            assert Path(result.screenshot_path).exists()
        finally:
            _AUTH_REGISTRY.pop("mock_login", None)
            _REGISTRY.pop("mock_login", None)


@pytest.mark.asyncio
class TestAuthFailurePaths:
    async def test_bad_credentials_returns_failed(
        self, auth_mock_server, tmp_path
    ) -> None:
        """Auth returns CREDENTIALS_INVALID → orchestrator returns FAILED."""
        from src.automation.auth.auth_registry import _AUTH_REGISTRY

        _AUTH_REGISTRY["mock_bad_creds"] = type(
            "PatchedBadCreds", (MockBadCredsStrategy,),
            {"__init__": lambda self: MockBadCredsStrategy.__init__(
                self, f"{auth_mock_server}/bad-creds"
            )},
        )
        _REGISTRY["mock_bad_creds"] = MockCancelStrategy

        try:
            sub = _mock_subscription(
                service_name="mock_bad_creds",
                cancellation_url=f"{auth_mock_server}/cancel",
            )
            credential = _make_credential(service_name="mock_bad_creds")

            orchestrator = CancellationOrchestrator(
                headless=True,
                timeout_ms=10_000,
                screenshot_dir=str(tmp_path),
            )
            result = await orchestrator.cancel(sub, credential=credential)

            assert result.success is False
            assert result.status == CancellationStatus.FAILED
            assert "Authentication failed" in result.error_message
        finally:
            _AUTH_REGISTRY.pop("mock_bad_creds", None)
            _REGISTRY.pop("mock_bad_creds", None)

    async def test_auth_timeout_returns_manual_required(
        self, auth_mock_server, tmp_path
    ) -> None:
        """Hidden Sign In button causes PlaywrightError → MANUAL_REQUIRED."""
        from src.automation.auth.auth_registry import _AUTH_REGISTRY

        _AUTH_REGISTRY["mock_timeout_auth"] = type(
            "PatchedTimeoutAuth", (MockTimeoutAuthStrategy,),
            {"__init__": lambda self: MockTimeoutAuthStrategy.__init__(
                self, f"{auth_mock_server}/timeout-login"
            )},
        )
        _REGISTRY["mock_timeout_auth"] = MockCancelStrategy

        try:
            fallback_url = "https://example.com/cancel"
            sub = _mock_subscription(
                service_name="mock_timeout_auth",
                cancellation_url=fallback_url,
            )
            credential = _make_credential(service_name="mock_timeout_auth")

            orchestrator = CancellationOrchestrator(
                headless=True,
                timeout_ms=5_000,
                screenshot_dir=str(tmp_path),
            )
            result = await orchestrator.cancel(sub, credential=credential)

            assert result.success is False
            assert result.status == CancellationStatus.MANUAL_REQUIRED
            assert result.fallback_url == fallback_url
            assert "Authentication error" in result.error_message
        finally:
            _AUTH_REGISTRY.pop("mock_timeout_auth", None)
            _REGISTRY.pop("mock_timeout_auth", None)

    async def test_no_auth_strategy_skips_to_cancel(
        self, auth_mock_server, tmp_path
    ) -> None:
        """No auth strategy registered → skip auth, proceed to cancel."""
        _REGISTRY["mock_no_auth"] = type(
            "PatchedNoAuthCancel", (MockCancelStrategy,),
            {"__init__": lambda self: MockCancelStrategy.__init__(
                self, f"{auth_mock_server}/cancel"
            )},
        )

        try:
            sub = _mock_subscription(
                service_name="mock_no_auth",
                cancellation_url=f"{auth_mock_server}/cancel",
            )
            credential = _make_credential(service_name="mock_no_auth")

            orchestrator = CancellationOrchestrator(
                headless=True,
                timeout_ms=10_000,
                screenshot_dir=str(tmp_path),
            )
            # Credential provided but no auth strategy → skip auth
            result = await orchestrator.cancel(sub, credential=credential)

            assert result.success is True
            assert result.status == CancellationStatus.SUCCESS
        finally:
            _REGISTRY.pop("mock_no_auth", None)
