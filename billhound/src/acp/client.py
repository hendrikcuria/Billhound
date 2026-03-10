"""
ACP client wrapper — typed config, wallet init, start/stop lifecycle.

Strict isolation: imports only from `virtuals_acp` and `src.config.settings`.
Knows nothing about cancellation, Telegram, or email ingestion.
"""
from __future__ import annotations

from typing import Callable

import structlog

from src.config.settings import Settings

logger = structlog.get_logger()


class BillhoundACPClient:
    """Wraps the Virtuals ACP SDK with Billhound-specific config.

    Lifecycle:
        client = BillhoundACPClient(settings, on_new_task_callback)
        client.start()   # Initializes SDK, begins listening for jobs
        ...
        client.stop()     # Cleanup
    """

    def __init__(self, settings: Settings, on_new_task: Callable) -> None:
        self._settings = settings
        self._on_new_task = on_new_task
        self._client: object | None = None

    def start(self) -> None:
        """Initialize the ACP SDK client. Call from main boot sequence."""
        from virtuals_acp import ACPContractClientV2, VirtualsACP

        wallet_key = self._settings.acp_wallet_private_key.get_secret_value()
        agent_address = self._settings.acp_agent_wallet_address
        entity_id = self._settings.acp_entity_id

        if not wallet_key or not agent_address or not entity_id:
            logger.error(
                "acp.config_incomplete",
                has_wallet_key=bool(wallet_key),
                has_agent_address=bool(agent_address),
                has_entity_id=bool(entity_id),
            )
            msg = "ACP requires wallet_private_key, agent_wallet_address, and entity_id"
            raise ValueError(msg)

        contract_client = ACPContractClientV2(
            wallet_private_key=wallet_key,
            agent_wallet_address=agent_address,
            entity_id=int(entity_id),
        )

        self._client = VirtualsACP(
            acp_contract_clients=contract_client,
            on_new_task=self._on_new_task,
        )

        logger.info(
            "acp.client_started",
            entity_id=entity_id,
            agent_address=agent_address,
        )

    def stop(self) -> None:
        """Cleanup — SDK doesn't expose a stop method, so we nil the reference."""
        if self._client is not None:
            logger.info("acp.client_stopped")
            self._client = None

    @property
    def is_running(self) -> bool:
        return self._client is not None
