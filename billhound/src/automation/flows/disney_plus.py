"""Disney+ cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

DISNEY_PLUS_CANCEL_URL = "https://www.disneyplus.com/account/subscription"


@register("disney+")
class DisneyPlusStrategy(BaseCancellationStrategy):
    """
    Automates Disney+ subscription cancellation.

    Flow:
    1. Navigate to account subscription page.
    2. Click "Cancel Subscription" (get_by_role).
    3. Click "Continue to Cancel" (get_by_role).
    4. Click second "Cancel Subscription" confirmation (get_by_role).
    5. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "disney+"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or DISNEY_PLUS_CANCEL_URL

        logger.info("automation.disney_plus.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Cancel Subscription"
        cancel_btn = page.get_by_role("button", name="Cancel Subscription").first
        await cancel_btn.wait_for(state="visible")
        await cancel_btn.click()

        logger.info("automation.disney_plus.clicked_cancel")

        # Step 2: Click "Continue to Cancel"
        continue_btn = page.get_by_role("button", name="Continue to Cancel")
        await continue_btn.wait_for(state="visible")
        await continue_btn.click()

        logger.info("automation.disney_plus.clicked_continue")

        # Step 3: Click final "Cancel Subscription" confirmation
        confirm_btn = page.get_by_role("button", name="Cancel Subscription").first
        await confirm_btn.wait_for(state="visible")
        await confirm_btn.click()

        logger.info("automation.disney_plus.clicked_confirm")

        # Step 4: Verify cancellation confirmed
        confirmation = page.get_by_text("cancelled", exact=False)
        await confirmation.wait_for(state="visible")

        logger.info("automation.disney_plus.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
