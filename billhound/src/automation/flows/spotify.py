"""Spotify Premium cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

SPOTIFY_CANCEL_URL = "https://www.spotify.com/account/overview/"


@register("spotify")
class SpotifyStrategy(BaseCancellationStrategy):
    """
    Automates Spotify Premium cancellation.

    Flow:
    1. Navigate to account overview page.
    2. Click "Cancel Premium" (get_by_role).
    3. Click "Yes, cancel" confirmation (get_by_role).
    4. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "spotify"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or SPOTIFY_CANCEL_URL

        logger.info("automation.spotify.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Cancel Premium"
        cancel_btn = page.get_by_role("button", name="Cancel Premium")
        await cancel_btn.wait_for(state="visible")
        await cancel_btn.click()

        logger.info("automation.spotify.clicked_cancel")

        # Step 2: Click "Yes, cancel" confirmation
        confirm_btn = page.get_by_role("button", name="Yes, cancel")
        await confirm_btn.wait_for(state="visible")
        await confirm_btn.click()

        logger.info("automation.spotify.clicked_confirm")

        # Step 3: Verify cancellation confirmed
        confirmation = page.get_by_text("cancelled", exact=False)
        await confirmation.wait_for(state="visible")

        logger.info("automation.spotify.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
