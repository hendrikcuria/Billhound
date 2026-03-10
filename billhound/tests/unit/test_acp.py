"""
Tests for Phase 8: Virtuals ACP Integration.

All ACP SDK objects are mocked — no real blockchain calls.

Covers:
  1. BillhoundACPClient — start/stop lifecycle, config validation
  2. CancellationAction — execute → deliverable dict, screenshot encoding
  3. ACPJobListener — phase routing, thread→async bridge, service extraction
"""
from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.acp.actions import CancellationAction
from src.acp.client import BillhoundACPClient
from src.acp.listener import ACPJobListener


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _make_settings(**overrides) -> MagicMock:
    """Build a mock Settings with ACP defaults + overrides."""
    from unittest.mock import PropertyMock

    from pydantic import SecretStr

    settings = MagicMock()
    settings.acp_enabled = overrides.get("acp_enabled", True)
    settings.acp_wallet_private_key = SecretStr(
        overrides.get("acp_wallet_private_key", "a" * 64)
    )
    settings.acp_agent_wallet_address = overrides.get(
        "acp_agent_wallet_address", "0x" + "b" * 40
    )
    settings.acp_entity_id = overrides.get("acp_entity_id", "42")
    settings.playwright_headless = True
    settings.playwright_timeout_ms = 30_000
    settings.screenshot_dir = "data/screenshots"
    settings.confidence_threshold = 0.70
    return settings


def _make_mock_job(
    *,
    phase: str = "request",
    job_id: int = 1,
    requirement: dict | str | None = None,
) -> MagicMock:
    """Build a mock ACP job with given phase and requirement."""
    job = MagicMock()
    job.id = job_id
    job.phase = MagicMock()
    job.phase.value = phase
    job.requirement = requirement
    job.accept = MagicMock()
    job.reject = MagicMock()
    job.deliver = MagicMock()
    job.create_requirement = MagicMock()
    return job


def _make_mock_memo(*, next_phase: str) -> MagicMock:
    """Build a mock ACPMemo with a next_phase."""
    memo = MagicMock()
    memo.next_phase = MagicMock()
    memo.next_phase.value = next_phase
    return memo


# ═══════════════════════════════════════════════════════════════════
# 1. BillhoundACPClient Tests
# ═══════════════════════════════════════════════════════════════════


class TestBillhoundACPClient:
    """ACP client wrapper — lifecycle and config validation."""

    def test_start_creates_sdk_instance(self) -> None:
        """start() should create VirtualsACP with correct args."""
        settings = _make_settings()
        callback = MagicMock()

        mock_acp_cls = MagicMock()
        mock_contract_cls = MagicMock()

        # Lazy imports inside start() → mock via sys.modules
        fake_module = MagicMock(
            VirtualsACP=mock_acp_cls,
            ACPContractClientV2=mock_contract_cls,
        )
        with patch.dict("sys.modules", {"virtuals_acp": fake_module}):
            client = BillhoundACPClient(settings, callback)
            client.start()

            mock_contract_cls.assert_called_once_with(
                wallet_private_key="a" * 64,
                agent_wallet_address="0x" + "b" * 40,
                entity_id=int("42"),
            )
            mock_acp_cls.assert_called_once()
            assert client.is_running is True

    def test_start_raises_on_missing_config(self) -> None:
        """start() should raise ValueError if ACP config is incomplete."""
        settings = _make_settings(acp_wallet_private_key="")
        fake_module = MagicMock()

        with patch.dict("sys.modules", {"virtuals_acp": fake_module}):
            client = BillhoundACPClient(settings, MagicMock())
            with pytest.raises(ValueError, match="ACP requires"):
                client.start()

    def test_stop_clears_client_reference(self) -> None:
        """stop() should nil the internal client reference."""
        settings = _make_settings()
        client = BillhoundACPClient(settings, MagicMock())
        client._client = MagicMock()  # Simulate running state
        assert client.is_running is True

        client.stop()
        assert client.is_running is False

    def test_is_running_false_before_start(self) -> None:
        """is_running should be False before start() is called."""
        settings = _make_settings()
        client = BillhoundACPClient(settings, MagicMock())
        assert client.is_running is False


# ═══════════════════════════════════════════════════════════════════
# 2. CancellationAction Tests
# ═══════════════════════════════════════════════════════════════════


class TestCancellationAction:
    """CancellationAction — bridges ACP job params to orchestrator results."""

    @pytest.mark.asyncio
    @patch("src.acp.actions.CancellationOrchestrator")
    @patch("src.acp.actions.has_strategy", return_value=True)
    async def test_action_returns_success_deliverable(
        self, mock_has_strategy, mock_orch_cls
    ) -> None:
        """Successful cancellation → deliverable with status='success'."""
        from src.automation.models import CancellationResult
        from src.config.constants import CancellationStatus

        mock_result = CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
            screenshot_path=None,
        )
        mock_orch = AsyncMock()
        mock_orch.cancel.return_value = mock_result
        mock_orch_cls.return_value = mock_orch

        settings = _make_settings()
        action = CancellationAction(settings, AsyncMock(), MagicMock())

        deliverable = await action.execute("netflix")

        assert deliverable["status"] == "success"
        assert deliverable["service"] == "netflix"
        assert deliverable["error"] is None
        mock_orch.cancel.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.acp.actions.CancellationOrchestrator")
    @patch("src.acp.actions.has_strategy", return_value=True)
    async def test_action_returns_failed_deliverable(
        self, mock_has_strategy, mock_orch_cls
    ) -> None:
        """Failed cancellation → deliverable with status='failed' + error."""
        from src.automation.models import CancellationResult
        from src.config.constants import CancellationStatus

        mock_result = CancellationResult(
            success=False,
            status=CancellationStatus.FAILED,
            error_message="Login failed",
        )
        mock_orch = AsyncMock()
        mock_orch.cancel.return_value = mock_result
        mock_orch_cls.return_value = mock_orch

        settings = _make_settings()
        action = CancellationAction(settings, AsyncMock(), MagicMock())

        deliverable = await action.execute("netflix")

        assert deliverable["status"] == "failed"
        assert deliverable["error"] == "Login failed"

    @pytest.mark.asyncio
    @patch("src.acp.actions.has_strategy", return_value=False)
    async def test_action_returns_manual_required_for_unsupported(
        self, mock_has_strategy
    ) -> None:
        """Unsupported service → deliverable with status='manual_required'."""
        settings = _make_settings()
        action = CancellationAction(settings, AsyncMock(), MagicMock())

        deliverable = await action.execute("some_unknown_service")

        assert deliverable["status"] == "manual_required"
        assert "not supported" in (deliverable["error"] or "").lower() or \
               "no automation" in (deliverable["error"] or "").lower()
        assert deliverable["service"] == "some_unknown_service"

    @pytest.mark.asyncio
    @patch("src.acp.actions.CancellationOrchestrator")
    @patch("src.acp.actions.has_strategy", return_value=True)
    async def test_action_screenshot_base64_encoding(
        self, mock_has_strategy, mock_orch_cls, tmp_path
    ) -> None:
        """PNG screenshot bytes → base64 string round-trip in deliverable."""
        from src.automation.models import CancellationResult
        from src.config.constants import CancellationStatus

        # Create a fake PNG screenshot
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        screenshot_file = tmp_path / "test_screenshot.png"
        screenshot_file.write_bytes(fake_png)

        mock_result = CancellationResult(
            success=True,
            status=CancellationStatus.SUCCESS,
            screenshot_path=str(screenshot_file),
        )
        mock_orch = AsyncMock()
        mock_orch.cancel.return_value = mock_result
        mock_orch_cls.return_value = mock_orch

        settings = _make_settings()
        action = CancellationAction(settings, AsyncMock(), MagicMock())

        deliverable = await action.execute("netflix")

        assert deliverable["status"] == "success"
        assert deliverable["screenshot_base64"] is not None
        # Verify round-trip
        decoded = base64.b64decode(deliverable["screenshot_base64"])
        assert decoded == fake_png

    @pytest.mark.asyncio
    @patch("src.acp.actions.CancellationOrchestrator")
    @patch("src.acp.actions.has_strategy", return_value=True)
    async def test_action_handles_orchestrator_exception(
        self, mock_has_strategy, mock_orch_cls
    ) -> None:
        """Orchestrator raises → deliverable with status='failed'."""
        mock_orch = AsyncMock()
        mock_orch.cancel.side_effect = RuntimeError("Browser crashed")
        mock_orch_cls.return_value = mock_orch

        settings = _make_settings()
        action = CancellationAction(settings, AsyncMock(), MagicMock())

        deliverable = await action.execute("netflix")

        assert deliverable["status"] == "failed"
        assert deliverable["error"] is not None


# ═══════════════════════════════════════════════════════════════════
# 3. ACPJobListener Tests
# ═══════════════════════════════════════════════════════════════════


class TestACPJobListener:
    """ACPJobListener — phase routing, thread→async bridge."""

    @patch("src.acp.listener.has_strategy", return_value=True)
    def test_request_phase_accepts_supported_service(
        self, mock_has_strategy
    ) -> None:
        """REQUEST phase + supported service → job.accept() called."""
        action = MagicMock()
        loop = MagicMock()
        listener = ACPJobListener(action, loop)

        job = _make_mock_job(
            phase="request",
            requirement={"service_name": "netflix"},
        )
        memo = _make_mock_memo(next_phase="negotiation")

        listener.on_new_task(job, memo)

        job.accept.assert_called_once()
        job.create_requirement.assert_called_once()
        job.reject.assert_not_called()

    @patch("src.acp.listener.has_strategy", return_value=False)
    def test_request_phase_rejects_unsupported_service(
        self, mock_has_strategy
    ) -> None:
        """REQUEST phase + unsupported service → job.reject() called."""
        action = MagicMock()
        loop = MagicMock()
        listener = ACPJobListener(action, loop)

        job = _make_mock_job(
            phase="request",
            requirement={"service_name": "unknown_service"},
        )
        memo = _make_mock_memo(next_phase="negotiation")

        listener.on_new_task(job, memo)

        job.reject.assert_called_once()
        job.accept.assert_not_called()

    @patch("src.acp.listener.asyncio")
    @patch("src.acp.listener.has_strategy", return_value=True)
    def test_transaction_phase_schedules_execution(
        self, mock_has_strategy, mock_asyncio
    ) -> None:
        """TRANSACTION phase → run_coroutine_threadsafe called."""
        action = AsyncMock(spec=CancellationAction)
        loop = MagicMock()
        listener = ACPJobListener(action, loop)

        # Mock future so add_done_callback doesn't fail
        mock_future = MagicMock()
        mock_asyncio.run_coroutine_threadsafe.return_value = mock_future

        job = _make_mock_job(
            phase="transaction",
            requirement={"service_name": "netflix"},
        )
        memo = _make_mock_memo(next_phase="evaluation")

        listener.on_new_task(job, memo)

        mock_asyncio.run_coroutine_threadsafe.assert_called_once()
        # Verify it was scheduled on our loop
        call_args = mock_asyncio.run_coroutine_threadsafe.call_args
        assert call_args[0][1] is loop
        mock_future.add_done_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_and_deliver_success(self) -> None:
        """_execute_and_deliver calls action.execute and job.deliver."""
        action = AsyncMock(spec=CancellationAction)
        action.execute.return_value = {
            "status": "success",
            "service": "netflix",
            "screenshot_base64": None,
            "fallback_url": None,
            "error": None,
        }
        loop = asyncio.get_running_loop()
        listener = ACPJobListener(action, loop)

        job = _make_mock_job(phase="transaction")

        await listener._execute_and_deliver(job, "netflix")

        action.execute.assert_awaited_once_with("netflix")
        job.deliver.assert_called_once()
        delivered = job.deliver.call_args[0][0]
        assert delivered["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_and_deliver_handles_error(self) -> None:
        """If action.execute raises, deliver a failure dict."""
        action = AsyncMock(spec=CancellationAction)
        action.execute.side_effect = RuntimeError("Playwright crashed")
        loop = asyncio.get_running_loop()
        listener = ACPJobListener(action, loop)

        job = _make_mock_job(phase="transaction")

        await listener._execute_and_deliver(job, "netflix")

        job.deliver.assert_called_once()
        delivered = job.deliver.call_args[0][0]
        assert delivered["status"] == "failed"
        assert "error" in delivered

    def test_completed_phase_does_not_crash(self) -> None:
        """COMPLETED phase → logged, no exception."""
        action = MagicMock()
        loop = MagicMock()
        listener = ACPJobListener(action, loop)

        job = _make_mock_job(phase="completed")
        # No memo for completed phase
        listener.on_new_task(job, None)

        # No accept/reject/deliver should be called
        job.accept.assert_not_called()
        job.reject.assert_not_called()
        job.deliver.assert_not_called()

    def test_extract_service_name_from_dict(self) -> None:
        """requirement = {"service_name": "netflix"} → "netflix"."""
        job = _make_mock_job(requirement={"service_name": "netflix"})
        result = ACPJobListener._extract_service_name(job)
        assert result == "netflix"

    def test_extract_service_name_from_string(self) -> None:
        """requirement = "netflix" → "netflix"."""
        job = _make_mock_job(requirement="netflix")
        result = ACPJobListener._extract_service_name(job)
        assert result == "netflix"

    def test_extract_service_name_returns_none_for_missing(self) -> None:
        """No requirement attr → None."""
        job = MagicMock(spec=[])  # No attributes
        result = ACPJobListener._extract_service_name(job)
        assert result is None
