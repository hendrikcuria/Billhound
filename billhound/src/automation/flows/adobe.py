"""Adobe Creative Cloud cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

ADOBE_CANCEL_URL = "https://account.adobe.com/plans"


@register("adobe")
class AdobeStrategy(BaseCancellationStrategy):
    """
    Automates Adobe Creative Cloud plan cancellation.

    Flow:
    1. Navigate to plans page.
    2. Click "Manage plan" (get_by_role).
    3. Click "Cancel your plan" (get_by_role).
    4. Click "Continue" through retention offers (get_by_role).
    5. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "adobe"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or ADOBE_CANCEL_URL

        logger.info("automation.adobe.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Manage plan"
        manage_btn = page.get_by_role("button", name="Manage plan")
        await manage_btn.wait_for(state="visible")
        await manage_btn.click()

        logger.info("automation.adobe.clicked_manage")

        # Step 2: Click "Cancel your plan"
        cancel_btn = page.get_by_role("button", name="Cancel your plan")
        await cancel_btn.wait_for(state="visible")
        await cancel_btn.click()

        logger.info("automation.adobe.clicked_cancel")

        # Step 3: Click "Continue" through retention offers
        continue_btn = page.get_by_role("button", name="Continue")
        await continue_btn.wait_for(state="visible")
        await continue_btn.click()

        logger.info("automation.adobe.clicked_continue")

        # Step 4: Verify cancellation confirmed
        confirmation = page.get_by_text("cancelled", exact=False)
        await confirmation.wait_for(state="visible")

        logger.info("automation.adobe.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
