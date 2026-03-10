"""Netflix cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

NETFLIX_CANCEL_URL = "https://www.netflix.com/cancelplan"


@register("netflix")
class NetflixStrategy(BaseCancellationStrategy):
    """
    Automates Netflix membership cancellation.

    Flow:
    1. Navigate to the cancel plan page.
    2. Click the "Cancel Membership" button (get_by_role).
    3. Handle the "Finish Cancellation" confirmation (get_by_role).
    4. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "netflix"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or NETFLIX_CANCEL_URL

        logger.info("automation.netflix.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Cancel Membership" button
        cancel_btn = page.get_by_role("button", name="Cancel Membership")
        await cancel_btn.wait_for(state="visible")
        await cancel_btn.click()

        logger.info("automation.netflix.clicked_cancel")

        # Step 2: Click "Finish Cancellation" confirmation
        finish_btn = page.get_by_role("button", name="Finish Cancellation")
        await finish_btn.wait_for(state="visible")
        await finish_btn.click()

        logger.info("automation.netflix.clicked_finish")

        # Step 3: Verify cancellation confirmed
        confirmation = page.get_by_text("cancelled", exact=False)
        await confirmation.wait_for(state="visible")

        logger.info("automation.netflix.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
