"""Abstract base for all authentication flow strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from playwright.async_api import Page

from src.automation.auth.models import AuthResult


@dataclass(frozen=True, slots=True)
class DecryptedCredential:
    """
    Plaintext credential passed to auth strategies.

    Created at the orchestrator / handler level, never persisted.
    Strategies receive this, NOT the encrypted DB model.
    """

    username: str
    password: str
    service_name: str


class BaseAuthStrategy(ABC):
    """
    Each concrete strategy encapsulates the browser steps
    to authenticate with one specific service.

    Strategies receive an already-created Playwright Page
    and a DecryptedCredential. They must NOT manage
    browser lifecycle or encryption — that is the orchestrator's job.

    Use ONLY accessibility locators:
    - page.get_by_role()
    - page.get_by_label()
    - page.get_by_text()

    No CSS selectors. No XPath.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Lowercase canonical service name, e.g. 'netflix'."""
        ...

    @property
    def login_url(self) -> str | None:
        """Override to provide service-specific login URL."""
        return None

    @abstractmethod
    async def authenticate(
        self,
        page: Page,
        credential: DecryptedCredential,
    ) -> AuthResult:
        """
        Run the login flow on the given page.

        Must NOT catch PlaywrightError — let it propagate to the orchestrator.
        Must NOT manage browser lifecycle.
        """
        ...
