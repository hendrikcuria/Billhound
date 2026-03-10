"""
Tests for the Playwright cancellation automation subsystem.

Uses aiohttp to serve mock HTML pages and real Playwright to test
click-and-screenshot logic and graceful fallback — no production servers.
"""
from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import web

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.orchestrator import CancellationOrchestrator
from src.automation.registry import _REGISTRY, get_strategy, has_strategy
from src.config.constants import CancellationStatus

# ─── Mock HTML Pages ───────────────────────────────────────────────

HAPPY_PATH_HTML = """\
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

TIMEOUT_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Cancel Subscription</title></head>
<body>
  <h1>Loading...</h1>
  <button style="display:none;">Cancel Membership</button>
</body>
</html>
"""


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def unused_tcp_port():
    """Find an unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mock_server_app():
    app = web.Application()

    async def happy_handler(request: web.Request) -> web.Response:
        return web.Response(text=HAPPY_PATH_HTML, content_type="text/html")

    async def timeout_handler(request: web.Request) -> web.Response:
        return web.Response(text=TIMEOUT_HTML, content_type="text/html")

    app.router.add_get("/happy", happy_handler)
    app.router.add_get("/timeout", timeout_handler)
    return app


@pytest.fixture
async def mock_server(mock_server_app, unused_tcp_port):
    runner = web.AppRunner(mock_server_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()
    yield f"http://127.0.0.1:{unused_tcp_port}"
    await runner.cleanup()


# ─── Mock Subscription ────────────────────────────────────────────

def _mock_subscription(
    service_name: str = "Netflix",
    cancellation_url: str | None = None,
) -> MagicMock:
    sub = MagicMock()
    sub.service_name = service_name
    sub.cancellation_url = cancellation_url
    sub.id = "test-sub-id"
    sub.amount = 54.00
    sub.currency = "MYR"
    return sub


# ─── Mock Strategies (test-only, not in src/) ─────────────────────

class MockHappyStrategy(BaseCancellationStrategy):
    """Clicks through the happy-path mock HTML."""

    @property
    def name(self) -> str:
        return "mock_happy"

    async def execute(self, page, subscription):
        await page.goto(subscription.cancellation_url, wait_until="networkidle")

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


class MockTimeoutStrategy(BaseCancellationStrategy):
    """Tries to click a hidden button — will timeout."""

    @property
    def name(self) -> str:
        return "mock_timeout"

    async def execute(self, page, subscription):
        await page.goto(subscription.cancellation_url, wait_until="networkidle")

        # Button exists but is display:none — click will timeout
        cancel_btn = page.get_by_role("button", name="Cancel Membership")
        await cancel_btn.click(timeout=2000)

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )


# ─── Unit Tests (no Playwright) ───────────────────────────────────

class TestCancellationResult:
    def test_success_result(self) -> None:
        result = CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
            screenshot_path="/tmp/test.png",
        )
        assert result.success is True
        assert result.status == CancellationStatus.SUCCESS
        assert result.screenshot_path == "/tmp/test.png"
        assert result.fallback_url is None
        assert result.error_message is None

    def test_fallback_result(self) -> None:
        result = CancellationResult(
            success=False,
            status=CancellationStatus.MANUAL_REQUIRED,
            fallback_url="https://netflix.com/cancelplan",
            error_message="Button not found",
        )
        assert result.success is False
        assert result.fallback_url == "https://netflix.com/cancelplan"

    def test_frozen_immutable(self) -> None:
        result = CancellationResult(
            success=True, status=CancellationStatus.SUCCESS
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestStrategyRegistry:
    def test_netflix_registered(self) -> None:
        import src.automation.flows  # noqa: F401

        assert has_strategy("Netflix")
        assert has_strategy("netflix")
        assert has_strategy("  Netflix  ")

    def test_unknown_service(self) -> None:
        assert has_strategy("SomeUnknownService123") is False

    def test_get_strategy_returns_instance(self) -> None:
        import src.automation.flows  # noqa: F401

        strategy = get_strategy("netflix")
        assert strategy is not None
        assert strategy.name == "netflix"

    def test_get_strategy_unknown_returns_none(self) -> None:
        result = get_strategy("nonexistent_service_xyz")
        assert result is None


# ─── Integration Tests (real Playwright against mock server) ──────

@pytest.mark.asyncio
class TestOrchestratorHappyPath:
    async def test_successful_cancellation(self, mock_server, tmp_path) -> None:
        """Strategy clicks through mock, returns success + screenshot."""
        _REGISTRY["mock_happy"] = MockHappyStrategy

        try:
            sub = _mock_subscription(
                service_name="mock_happy",
                cancellation_url=f"{mock_server}/happy",
            )

            orchestrator = CancellationOrchestrator(
                headless=True,
                timeout_ms=10_000,
                screenshot_dir=str(tmp_path),
            )
            result = await orchestrator.cancel(sub)

            assert result.success is True
            assert result.status == CancellationStatus.SUCCESS
            assert result.screenshot_path is not None
            assert Path(result.screenshot_path).exists()
            assert result.error_message is None
        finally:
            _REGISTRY.pop("mock_happy", None)


@pytest.mark.asyncio
class TestOrchestratorGracefulFallback:
    async def test_timeout_returns_fallback(self, mock_server, tmp_path) -> None:
        """Hidden button causes timeout; returns fallback URL + screenshot."""
        _REGISTRY["mock_timeout"] = MockTimeoutStrategy

        try:
            fallback = f"{mock_server}/timeout"
            sub = _mock_subscription(
                service_name="mock_timeout",
                cancellation_url=fallback,
            )

            orchestrator = CancellationOrchestrator(
                headless=True,
                timeout_ms=5_000,
                screenshot_dir=str(tmp_path),
            )
            result = await orchestrator.cancel(sub)

            assert result.success is False
            assert result.status == CancellationStatus.MANUAL_REQUIRED
            assert result.fallback_url == fallback
            assert result.error_message is not None
            assert "Automation failed" in result.error_message
            # Screenshot of final page state should exist
            if result.screenshot_path:
                assert Path(result.screenshot_path).exists()
        finally:
            _REGISTRY.pop("mock_timeout", None)

    async def test_no_strategy_returns_manual_required(self, tmp_path) -> None:
        """Unknown service returns MANUAL_REQUIRED immediately, no browser."""
        sub = _mock_subscription(
            service_name="totally_unknown_service",
            cancellation_url="https://example.com/cancel",
        )

        orchestrator = CancellationOrchestrator(
            headless=True,
            timeout_ms=5_000,
            screenshot_dir=str(tmp_path),
        )
        result = await orchestrator.cancel(sub)

        assert result.success is False
        assert result.status == CancellationStatus.MANUAL_REQUIRED
        assert result.fallback_url == "https://example.com/cancel"
        assert "No automation available" in result.error_message
