"""Abstract base for all cancellation flow strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod

from playwright.async_api import Page

from src.automation.models import CancellationResult
from src.db.models.subscription import Subscription


class BaseCancellationStrategy(ABC):
    """
    Each concrete strategy encapsulates the browser steps
    to cancel one specific service.

    Strategies receive an already-navigated Playwright Page
    and the Subscription ORM instance. They must NOT manage
    browser lifecycle — that is the orchestrator's job.

    Strategies should NOT catch PlaywrightError — let it propagate
    to the orchestrator for graceful fallback handling.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Lowercase canonical service name, e.g. 'netflix'."""
        ...

    @abstractmethod
    async def execute(
        self,
        page: Page,
        subscription: Subscription,
    ) -> CancellationResult:
        """
        Run the cancellation flow.

        Use ONLY accessibility locators:
        - page.get_by_role()
        - page.get_by_label()
        - page.get_by_text()

        No CSS selectors. No XPath.
        """
        ...
