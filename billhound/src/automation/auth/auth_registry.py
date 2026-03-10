"""Registry mapping service names to their authentication strategy classes."""
from __future__ import annotations

import structlog

from src.automation.auth.base_auth_strategy import BaseAuthStrategy

logger = structlog.get_logger()

_AUTH_REGISTRY: dict[str, type[BaseAuthStrategy]] = {}


def auth_register(name: str):
    """
    Decorator factory that registers an auth strategy class under a given name.

    Usage::

        @auth_register("netflix")
        class NetflixAuthStrategy(BaseAuthStrategy):
            ...
    """

    def decorator(
        cls: type[BaseAuthStrategy],
    ) -> type[BaseAuthStrategy]:
        key = name.lower().strip()
        if key in _AUTH_REGISTRY:
            logger.warning("auth_strategy.registry.overwrite", name=key)
        _AUTH_REGISTRY[key] = cls
        logger.debug("auth_strategy.registry.registered", name=key)
        return cls

    return decorator


def get_auth_strategy(service_name: str) -> BaseAuthStrategy | None:
    """Look up and instantiate an auth strategy. Returns None if not registered."""
    key = service_name.lower().strip()
    cls = _AUTH_REGISTRY.get(key)
    if cls is None:
        return None
    return cls()


def has_auth_strategy(service_name: str) -> bool:
    """Check whether an auth strategy exists for a service."""
    return service_name.lower().strip() in _AUTH_REGISTRY


def list_auth_supported_services() -> list[str]:
    """Return sorted list of service names with auth support."""
    return sorted(_AUTH_REGISTRY.keys())
