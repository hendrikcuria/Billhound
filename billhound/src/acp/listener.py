"""
ACP job listener — routes incoming Virtuals network jobs to local execution.

The ACP SDK fires ``on_new_task`` from a background thread. This listener
bridges into our asyncio event loop using ``asyncio.run_coroutine_threadsafe()``.

Thread safety: only the ``on_new_task`` method runs on the SDK's thread.
All async work (_execute_and_deliver) runs on the main event loop.
"""
from __future__ import annotations

import asyncio

import structlog

from src.acp.actions import CancellationAction
from src.automation.registry import has_strategy

logger = structlog.get_logger()


class ACPJobListener:
    """Background listener that routes incoming ACP jobs to local execution.

    ACP job lifecycle phases handled:
        REQUEST      → accept or reject based on strategy availability
        TRANSACTION  → payment received, execute cancellation + deliver result
        COMPLETED    → log completion
        REJECTED     → log rejection
    """

    def __init__(
        self,
        action: CancellationAction,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._action = action
        self._loop = loop

    def on_new_task(self, job: object, memo_to_sign: object | None = None) -> None:
        """ACP SDK callback — runs on SDK's internal thread, NOT our event loop.

        Parameters
        ----------
        job:
            An ``ACPJob`` instance with ``.phase``, ``.id``, ``.accept()``,
            ``.reject()``, ``.deliver()``, ``.create_requirement()`` methods.
        memo_to_sign:
            An ``ACPMemo`` with ``.next_phase`` when a phase transition is requested.
        """
        try:
            phase = self._get_phase(job)
            next_phase = self._get_next_phase(memo_to_sign) if memo_to_sign else None

            logger.info(
                "acp.job.received",
                job_id=getattr(job, "id", "unknown"),
                phase=phase,
                next_phase=next_phase,
            )

            if phase == "request" and next_phase == "negotiation":
                self._handle_request(job)
            elif phase == "transaction" and next_phase == "evaluation":
                self._handle_transaction(job)
            elif phase == "completed":
                logger.info("acp.job.completed", job_id=getattr(job, "id", "unknown"))
            elif phase == "rejected":
                logger.info("acp.job.rejected", job_id=getattr(job, "id", "unknown"))
            else:
                logger.debug(
                    "acp.job.unhandled_phase",
                    job_id=getattr(job, "id", "unknown"),
                    phase=phase,
                    next_phase=next_phase,
                )
        except Exception:
            logger.exception(
                "acp.job.callback_error",
                job_id=getattr(job, "id", "unknown"),
            )

    # ------------------------------------------------------------------
    # Phase handlers
    # ------------------------------------------------------------------

    def _handle_request(self, job: object) -> None:
        """REQUEST phase: accept if we have a strategy, reject otherwise."""
        service_name = self._extract_service_name(job)

        if service_name and has_strategy(service_name):
            job.accept(f"Billhound can cancel {service_name}")  # type: ignore[attr-defined]
            job.create_requirement(  # type: ignore[attr-defined]
                f"Cancellation of {service_name} accepted, awaiting payment"
            )
            logger.info(
                "acp.job.accepted",
                job_id=getattr(job, "id", "unknown"),
                service=service_name,
            )
        else:
            reason = f"Service '{service_name}' not supported by Billhound"
            job.reject(reason)  # type: ignore[attr-defined]
            logger.info(
                "acp.job.rejected_unsupported",
                job_id=getattr(job, "id", "unknown"),
                service=service_name,
            )

    def _handle_transaction(self, job: object) -> None:
        """TRANSACTION phase: payment received — execute cancellation async."""
        service_name = self._extract_service_name(job)

        if not service_name:
            logger.error(
                "acp.job.no_service_name",
                job_id=getattr(job, "id", "unknown"),
            )
            job.deliver(  # type: ignore[attr-defined]
                {"status": "failed", "error": "No service_name in job requirement"}
            )
            return

        # Bridge from SDK thread → our asyncio event loop
        future = asyncio.run_coroutine_threadsafe(
            self._execute_and_deliver(job, service_name),
            self._loop,
        )
        # Log any unexpected errors from the future (fire-and-forget)
        future.add_done_callback(self._future_error_handler)

    # ------------------------------------------------------------------
    # Async execution bridge
    # ------------------------------------------------------------------

    async def _execute_and_deliver(self, job: object, service_name: str) -> None:
        """Async execution — runs on our event loop, not the SDK thread."""
        job_id = getattr(job, "id", "unknown")
        try:
            deliverable = await self._action.execute(service_name)
            job.deliver(deliverable)  # type: ignore[attr-defined]
            logger.info(
                "acp.job.delivered",
                job_id=job_id,
                status=deliverable.get("status"),
                service=service_name,
            )
        except Exception:
            logger.exception("acp.job.execution_failed", job_id=job_id)
            try:
                job.deliver(  # type: ignore[attr-defined]
                    {
                        "status": "failed",
                        "service": service_name,
                        "error": "Internal execution error",
                    }
                )
            except Exception:
                logger.exception("acp.job.deliver_failed", job_id=job_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_service_name(job: object) -> str | None:
        """Pull service_name from the job's requirement dict or string."""
        req = getattr(job, "requirement", None)
        if req is None:
            # Also check service_requirement (some SDK versions)
            req = getattr(job, "service_requirement", None)
        if isinstance(req, dict):
            return req.get("service_name")
        if isinstance(req, str):
            return req
        return None

    @staticmethod
    def _get_phase(job: object) -> str:
        """Extract phase string from job, handling both enum and string values."""
        phase = getattr(job, "phase", None)
        if phase is None:
            return "unknown"
        # Handle enum (ACPJobPhase) or plain string
        return str(getattr(phase, "value", phase)).lower()

    @staticmethod
    def _get_next_phase(memo: object) -> str | None:
        """Extract next_phase from memo, handling both enum and string values."""
        next_phase = getattr(memo, "next_phase", None)
        if next_phase is None:
            return None
        return str(getattr(next_phase, "value", next_phase)).lower()

    @staticmethod
    def _future_error_handler(future: asyncio.Future) -> None:  # type: ignore[type-arg]
        """Log unhandled exceptions from fire-and-forget futures."""
        try:
            exc = future.exception()
            if exc:
                logger.error(
                    "acp.job.future_error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
        except asyncio.CancelledError:
            pass
