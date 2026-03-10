"""
Orchestrates Playwright lifecycle, screenshot capture, and graceful fallback
around individual cancellation strategies.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import structlog
from playwright.async_api import Error as PlaywrightError, async_playwright

from src.automation.auth.auth_registry import get_auth_strategy
from src.automation.auth.base_auth_strategy import DecryptedCredential
from src.automation.models import CancellationResult
from src.automation.registry import get_strategy
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()


class CancellationOrchestrator:
    """
    Manages browser lifecycle and delegates to the correct strategy.

    Never raises to its caller — always returns a CancellationResult.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 30_000,
        screenshot_dir: str = "data/screenshots",
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._screenshot_dir = Path(screenshot_dir)

    async def cancel(
        self,
        subscription: Subscription,
        credential: DecryptedCredential | None = None,
    ) -> CancellationResult:
        """Attempt automated cancellation. Always returns, never raises."""
        strategy = get_strategy(subscription.service_name)
        if strategy is None:
            return CancellationResult(
                success=False,
                status=CancellationStatus.MANUAL_REQUIRED,
                fallback_url=subscription.cancellation_url,
                error_message=(
                    f"No automation available for {subscription.service_name}"
                ),
            )

        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            try:
                context = await browser.new_context()
                context.set_default_timeout(self._timeout_ms)
                page = await context.new_page()

                # ── Phase 1: Authentication ──
                if credential is not None:
                    auth_strategy = get_auth_strategy(
                        subscription.service_name
                    )
                    if auth_strategy is not None:
                        try:
                            auth_result = await auth_strategy.authenticate(
                                page, credential
                            )
                            if not auth_result.success:
                                logger.warning(
                                    "automation.auth_failed",
                                    service=subscription.service_name,
                                    status=auth_result.status.value,
                                )
                                screenshot_path = await self._safe_screenshot(
                                    page, subscription.service_name
                                )
                                return CancellationResult(
                                    success=False,
                                    status=CancellationStatus.FAILED,
                                    screenshot_path=screenshot_path,
                                    fallback_url=subscription.cancellation_url,
                                    error_message=(
                                        f"Authentication failed: "
                                        f"{auth_result.error_message}"
                                    ),
                                )
                            logger.info(
                                "automation.auth_success",
                                service=subscription.service_name,
                            )
                        except PlaywrightError as exc:
                            logger.warning(
                                "automation.auth_playwright_error",
                                service=subscription.service_name,
                                error=str(exc),
                            )
                            screenshot_path = await self._safe_screenshot(
                                page, subscription.service_name
                            )
                            return CancellationResult(
                                success=False,
                                status=CancellationStatus.MANUAL_REQUIRED,
                                screenshot_path=screenshot_path,
                                fallback_url=subscription.cancellation_url,
                                error_message=f"Authentication error: {exc}",
                            )

                # ── Phase 2: Cancellation ──
                try:
                    result = await strategy.execute(page, subscription)

                    screenshot_path = self._screenshot_name(
                        subscription.service_name, "success"
                    )
                    await page.screenshot(path=screenshot_path, full_page=True)

                    return replace(result, screenshot_path=screenshot_path)

                except PlaywrightError as exc:
                    logger.warning(
                        "automation.playwright_error",
                        service=subscription.service_name,
                        error=str(exc),
                    )
                    screenshot_path = await self._safe_screenshot(
                        page, subscription.service_name
                    )
                    return CancellationResult(
                        success=False,
                        status=CancellationStatus.MANUAL_REQUIRED,
                        screenshot_path=screenshot_path,
                        fallback_url=subscription.cancellation_url,
                        error_message=f"Automation failed: {exc}",
                    )

                except Exception as exc:
                    logger.exception(
                        "automation.unexpected_error",
                        service=subscription.service_name,
                    )
                    screenshot_path = await self._safe_screenshot(
                        page, subscription.service_name
                    )
                    return CancellationResult(
                        success=False,
                        status=CancellationStatus.FAILED,
                        screenshot_path=screenshot_path,
                        fallback_url=subscription.cancellation_url,
                        error_message=f"Unexpected error: {exc}",
                    )

            finally:
                await browser.close()

    def _screenshot_name(self, service_name: str, suffix: str) -> str:
        """Generate unique screenshot path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = service_name.lower().replace(" ", "_")
        filename = f"{safe_name}_{suffix}_{ts}_{uuid.uuid4().hex[:8]}.png"
        return str(self._screenshot_dir / filename)

    async def _safe_screenshot(
        self, page, service_name: str
    ) -> str | None:
        """Attempt screenshot; return None if that also fails."""
        try:
            path = self._screenshot_name(service_name, "fallback")
            await page.screenshot(path=path, full_page=True)
            return path
        except Exception:
            logger.warning("automation.screenshot_failed", service=service_name)
            return None
