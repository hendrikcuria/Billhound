"""Microsoft 365 cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

MICROSOFT365_CANCEL_URL = "https://account.microsoft.com/services"


@register("microsoft 365")
class Microsoft365Strategy(BaseCancellationStrategy):
    """
    Automates Microsoft 365 subscription cancellation.

    Flow:
    1. Navigate to services page.
    2. Click "Manage" (get_by_role).
    3. Click "Cancel subscription" (get_by_role).
    4. Click "Confirm cancellation" (get_by_role).
    5. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "microsoft 365"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or MICROSOFT365_CANCEL_URL

        logger.info("automation.microsoft365.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Manage"
        manage_btn = page.get_by_role("link", name="Manage").first
        await manage_btn.wait_for(state="visible")
        await manage_btn.click()

        logger.info("automation.microsoft365.clicked_manage")

        # Step 2: Click "Cancel subscription"
        cancel_btn = page.get_by_role("button", name="Cancel subscription")
        await cancel_btn.wait_for(state="visible")
        await cancel_btn.click()

        logger.info("automation.microsoft365.clicked_cancel")

        # Step 3: Click "Confirm cancellation"
        confirm_btn = page.get_by_role("button", name="Confirm cancellation")
        await confirm_btn.wait_for(state="visible")
        await confirm_btn.click()

        logger.info("automation.microsoft365.clicked_confirm")

        # Step 4: Verify cancellation confirmed
        confirmation = page.get_by_text("cancelled", exact=False).or_(
            page.get_by_text("turned off", exact=False)
        )
        await confirmation.wait_for(state="visible")

        logger.info("automation.microsoft365.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
