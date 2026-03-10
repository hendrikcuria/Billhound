"""YouTube Premium cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

YOUTUBE_PREMIUM_CANCEL_URL = "https://www.youtube.com/paid_memberships"


@register("youtube premium")
class YoutubePremiumStrategy(BaseCancellationStrategy):
    """
    Automates YouTube Premium cancellation.

    Flow:
    1. Navigate to paid memberships page.
    2. Click "Deactivate" or "Manage membership" (get_by_role).
    3. Click "Continue to cancel" (get_by_role).
    4. Click "Yes, cancel" confirmation (get_by_role).
    5. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "youtube premium"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or YOUTUBE_PREMIUM_CANCEL_URL

        logger.info("automation.youtube_premium.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Deactivate" (primary) or "Manage membership" (fallback)
        deactivate_btn = page.get_by_role("button", name="Deactivate").or_(
            page.get_by_role("button", name="Manage membership")
        )
        await deactivate_btn.wait_for(state="visible")
        await deactivate_btn.click()

        logger.info("automation.youtube_premium.clicked_deactivate")

        # Step 2: Click "Continue to cancel"
        continue_btn = page.get_by_role("button", name="Continue to cancel")
        await continue_btn.wait_for(state="visible")
        await continue_btn.click()

        logger.info("automation.youtube_premium.clicked_continue")

        # Step 3: Click "Yes, cancel"
        confirm_btn = page.get_by_role("button", name="Yes, cancel")
        await confirm_btn.wait_for(state="visible")
        await confirm_btn.click()

        logger.info("automation.youtube_premium.clicked_confirm")

        # Step 4: Verify cancellation confirmed
        confirmation = page.get_by_text("cancelled", exact=False)
        await confirmation.wait_for(state="visible")

        logger.info("automation.youtube_premium.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
