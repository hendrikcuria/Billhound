"""NordVPN cancellation flow strategy."""
from __future__ import annotations

import structlog
from playwright.async_api import Page

from src.automation.base_strategy import BaseCancellationStrategy
from src.automation.models import CancellationResult
from src.automation.registry import register
from src.config.constants import CancellationStatus
from src.db.models.subscription import Subscription

logger = structlog.get_logger()

NORDVPN_CANCEL_URL = "https://my.nordaccount.com/dashboard/nordvpn/"


@register("nordvpn")
class NordvpnStrategy(BaseCancellationStrategy):
    """
    Automates NordVPN auto-renewal cancellation.

    Flow:
    1. Navigate to NordVPN dashboard.
    2. Click "Cancel automatic payments" (get_by_role).
    3. Click "Cancel auto-renewal" confirmation (get_by_role).
    4. Verify the confirmation text appears.
    """

    @property
    def name(self) -> str:
        return "nordvpn"

    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        cancel_url = subscription.cancellation_url or NORDVPN_CANCEL_URL

        logger.info("automation.nordvpn.start", url=cancel_url)
        await page.goto(cancel_url, wait_until="networkidle")

        # Step 1: Click "Cancel automatic payments"
        cancel_btn = page.get_by_role("button", name="Cancel automatic payments")
        await cancel_btn.wait_for(state="visible")
        await cancel_btn.click()

        logger.info("automation.nordvpn.clicked_cancel")

        # Step 2: Click "Cancel auto-renewal" confirmation
        confirm_btn = page.get_by_role("button", name="Cancel auto-renewal")
        await confirm_btn.wait_for(state="visible")
        await confirm_btn.click()

        logger.info("automation.nordvpn.clicked_confirm")

        # Step 3: Verify cancellation confirmed
        confirmation = page.get_by_text("auto-renewal is off", exact=False).or_(
            page.get_by_text("cancelled", exact=False)
        )
        await confirmation.wait_for(state="visible")

        logger.info("automation.nordvpn.confirmed")

        return CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
        )
