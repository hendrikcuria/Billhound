"""Data types for the cancellation automation subsystem."""
from __future__ import annotations

from dataclasses import dataclass

from src.config.constants import CancellationStatus


@dataclass(frozen=True, slots=True)
class CancellationResult:
    """Immutable outcome of a cancellation strategy execution."""

    success: bool
    status: CancellationStatus
    screenshot_path: str | None = None
    fallback_url: str | None = None
    error_message: str | None = None
