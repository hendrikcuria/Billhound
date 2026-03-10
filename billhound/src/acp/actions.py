"""
Cancellation action — bridges ACP job parameters to CancellationOrchestrator.

This is the *only* file that touches both the ACP layer and the web2
cancellation engine. It translates between the two worlds:

    ACP job params  →  CancellationOrchestrator  →  deliverable dict
"""
from __future__ import annotations

import base64
import uuid
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.automation.models import CancellationResult
from src.automation.orchestrator import CancellationOrchestrator
from src.automation.registry import has_strategy, list_supported_services
from src.config.settings import Settings
from src.trust.encryption import EncryptionService

logger = structlog.get_logger()


class CancellationAction:
    """Bridges ACP job parameters → CancellationOrchestrator → deliverable dict.

    Returns a JSON-serializable dict suitable for ``job.deliver()``.
    Screenshot bytes are base64-encoded inline (not filesystem paths).
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        encryption: EncryptionService,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._encryption = encryption

    async def execute(
        self,
        service_name: str,
        user_id: uuid.UUID | None = None,
    ) -> dict:
        """Run the cancellation flow for a service and return an ACP deliverable.

        Parameters
        ----------
        service_name:
            Canonical service name, e.g. ``"netflix"``.
        user_id:
            Optional — if provided, look up stored credentials for login.

        Returns
        -------
        dict with keys:
            ``status``: ``"success"`` | ``"failed"`` | ``"manual_required"``
            ``service``: the service name
            ``screenshot_base64``: base64 PNG string or None
            ``fallback_url``: manual cancellation URL or None
            ``error``: error message or None
        """
        service_key = service_name.lower().strip()

        if not has_strategy(service_key):
            logger.warning("acp.action.no_strategy", service=service_key)
            return self._build_deliverable(
                service=service_key,
                status="manual_required",
                error=f"No automation strategy for '{service_key}'",
                fallback_url=self._guess_cancellation_url(service_key),
            )

        # Build a minimal subscription-like object for the orchestrator
        subscription = self._build_mock_subscription(service_key)

        # Look up stored credentials if user_id provided
        credential = None
        if user_id:
            credential = await self._lookup_credential(user_id, service_key)

        orchestrator = CancellationOrchestrator(
            headless=self._settings.playwright_headless,
            timeout_ms=self._settings.playwright_timeout_ms,
            screenshot_dir=self._settings.screenshot_dir,
        )

        try:
            result = await orchestrator.cancel(subscription, credential)
        except Exception:
            logger.exception("acp.action.orchestrator_error", service=service_key)
            return self._build_deliverable(
                service=service_key,
                status="failed",
                error="Internal cancellation error",
            )

        return self._result_to_deliverable(service_key, result)

    def get_supported_services(self) -> list[str]:
        """Return list of service names with automation support."""
        return list_supported_services()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _result_to_deliverable(
        self, service: str, result: CancellationResult
    ) -> dict:
        """Convert a CancellationResult to an ACP-compatible deliverable dict."""
        screenshot_b64 = None
        if result.screenshot_path:
            screenshot_b64 = self._encode_screenshot(result.screenshot_path)

        return self._build_deliverable(
            service=service,
            status=result.status.value,
            screenshot_base64=screenshot_b64,
            fallback_url=result.fallback_url,
            error=result.error_message,
        )

    @staticmethod
    def _build_deliverable(
        *,
        service: str,
        status: str,
        screenshot_base64: str | None = None,
        fallback_url: str | None = None,
        error: str | None = None,
    ) -> dict:
        return {
            "status": status,
            "service": service,
            "screenshot_base64": screenshot_base64,
            "fallback_url": fallback_url,
            "error": error,
        }

    @staticmethod
    def _encode_screenshot(path: str) -> str | None:
        """Read a PNG screenshot file and return base64-encoded string."""
        try:
            screenshot_path = Path(path)
            if screenshot_path.exists():
                raw = screenshot_path.read_bytes()
                return base64.b64encode(raw).decode("ascii")
        except Exception:
            logger.exception("acp.action.screenshot_encode_failed", path=path)
        return None

    @staticmethod
    def _build_mock_subscription(service_name: str) -> object:
        """Build a minimal object with the fields CancellationOrchestrator needs.

        The orchestrator expects ``subscription.service_name`` and optionally
        ``subscription.cancellation_url``.
        """

        class _MockSubscription:
            def __init__(self, name: str) -> None:
                self.id = uuid.uuid4()
                self.service_name = name
                self.cancellation_url: str | None = None

        return _MockSubscription(service_name)

    async def _lookup_credential(
        self, user_id: uuid.UUID, service_name: str
    ) -> object | None:
        """Look up and decrypt stored credentials for a service.

        Returns a DecryptedCredential or None.
        """
        try:
            from src.automation.auth.base_auth_strategy import DecryptedCredential
            from src.db.repositories.service_credential_repo import (
                ServiceCredentialRepository,
            )

            async with self._session_factory() as session:
                repo = ServiceCredentialRepository(session, self._encryption)
                cred = await repo.get_by_user_and_service(user_id, service_name)
                if cred:
                    return DecryptedCredential(
                        username=self._encryption.decrypt(cred.username_encrypted),
                        password=self._encryption.decrypt(cred.password_encrypted),
                        service_name=service_name,
                    )
        except Exception:
            logger.exception(
                "acp.action.credential_lookup_failed",
                user_id=str(user_id),
                service=service_name,
            )
        return None

    @staticmethod
    def _guess_cancellation_url(service_name: str) -> str | None:
        """Best-effort URL for manual cancellation (fallback)."""
        urls: dict[str, str] = {
            "netflix": "https://www.netflix.com/cancelplan",
            "spotify": "https://www.spotify.com/account/subscription/",
            "disney+": "https://www.disneyplus.com/account",
            "hulu": "https://secure.hulu.com/account",
            "adobe": "https://account.adobe.com/plans",
            "youtube premium": "https://www.youtube.com/paid_memberships",
        }
        return urls.get(service_name.lower().strip())
