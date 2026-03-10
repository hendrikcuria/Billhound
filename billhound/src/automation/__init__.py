"""
Playwright-based subscription cancellation automation.

Public API:
    CancellationOrchestrator - manages browser lifecycle
    CancellationResult       - immutable result dataclass
    has_strategy             - check if service has automation
"""
from src.automation.models import CancellationResult
from src.automation.orchestrator import CancellationOrchestrator
from src.automation.registry import has_strategy

# Import flows to trigger strategy registration
import src.automation.flows  # noqa: F401

__all__ = [
    "CancellationOrchestrator",
    "CancellationResult",
    "has_strategy",
]
