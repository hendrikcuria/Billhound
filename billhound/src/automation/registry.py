"""
Registry mapping service names to their cancellation strategy classes.
"""
from __future__ import annotations

import structlog

from src.automation.base_strategy import BaseCancellationStrategy

logger = structlog.get_logger()

_REGISTRY: dict[str, type[BaseCancellationStrategy]] = {}


def register(name: str):
    """
    Decorator factory that registers a strategy class under a given name.

    Usage::

        @register("netflix")
        class NetflixStrategy(BaseCancellationStrategy):
            ...
    """

    def decorator(
        cls: type[BaseCancellationStrategy],
    ) -> type[BaseCancellationStrategy]:
        key = name.lower().strip()
        if key in _REGISTRY:
            logger.warning("strategy.registry.overwrite", name=key)
        _REGISTRY[key] = cls
        logger.debug("strategy.registry.registered", name=key)
        return cls

    return decorator


def get_strategy(service_name: str) -> BaseCancellationStrategy | None:
    """Look up and instantiate a strategy. Returns None if not registered."""
    key = service_name.lower().strip()
    cls = _REGISTRY.get(key)
    if cls is None:
        return None
    return cls()


def has_strategy(service_name: str) -> bool:
    """Check whether automation exists for a service without instantiating."""
    return service_name.lower().strip() in _REGISTRY


def list_supported_services() -> list[str]:
    """Return sorted list of service names with automation support."""
    return sorted(_REGISTRY.keys())
