"""Amazon Prime cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

AMAZON_PRIME_CANCEL_URL = "https://www.amazon.com/mc/pipeline/cancellation"


@register("amazon prime")
class AmazonPrimeStrategy(BaseCancellationStrategy):
    """
    Automates Amazon Prime membership cancellation.

    Flow:
    1. Navigate to Prime cancellation pipeline.
    2. Click "End Membership" (get_by_role).
    3. Click "Continue to Cancel" (get_by_role).
    4. Click final date-based confirmation (get_by_role).
    5. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "amazon prime"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or AMAZON_PRIME_CANCEL_URL

        logger.info("automation.amazon_prime.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "End Membership"
        end_btn = page.get_by_role("button", name="End Membership")
        await end_btn.wait_for(state="visible")
        await end_btn.click()

        logger.info("automation.amazon_prime.clicked_end")

        # Step 2: Click "Continue to Cancel"
        continue_btn = page.get_by_role("button", name="Continue to Cancel")
        await continue_btn.wait_for(state="visible")
        await continue_btn.click()

        logger.info("automation.amazon_prime.clicked_continue")

        # Step 3: Final confirmation — button text varies by date
        final_btn = page.get_by_role("button", name="End on")
        await final_btn.wait_for(state="visible")
        await final_btn.click()

        logger.info("automation.amazon_prime.clicked_final")

        # Step 4: Verify cancellation confirmed
        confirmation = page.get_by_text("ended", exact=False).or_(
            page.get_by_text("cancelled", exact=False)
        )
        await confirmation.wait_for(state="visible")

        logger.info("automation.amazon_prime.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
