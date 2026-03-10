"""
Tests verifying all 10 MVP services are registered in both registries.

No Playwright — pure unit tests against the registry dictionaries.
"""
from __future__ import annotations

import pytest

# Trigger registration of all strategies
import src.automation.flows  # noqa: F401
import src.automation.auth.flows  # noqa: F401

from src.automation.registry import (
    get_strategy,
    has_strategy,
    list_supported_services,
)
from src.automation.auth.auth_registry import (
    get_auth_strategy,
    has_auth_strategy,
    list_auth_supported_services,
)

# The 10 MVP services (Netflix + 9 new)
MVP_SERVICES = [
    "netflix",
    "spotify",
    "adobe",
    "canva",
    "amazon prime",
    "disney+",
    "youtube premium",
    "hulu",
    "microsoft 365",
    "nordvpn",
]


class TestCancelRegistryComplete:
    def test_all_10_cancel_strategies_registered(self) -> None:
        """Every MVP service has a cancellation strategy."""
        for service in MVP_SERVICES:
            assert has_strategy(service), f"Missing cancel strategy: {service}"

    def test_cancel_strategy_instantiation(self) -> None:
        """get_strategy() returns a valid instance for each service."""
        for service in MVP_SERVICES:
            strategy = get_strategy(service)
            assert strategy is not None, f"get_strategy returned None: {service}"

    def test_cancel_strategy_names_match_keys(self) -> None:
        """Each strategy's .name property matches its registry key."""
        for service in MVP_SERVICES:
            strategy = get_strategy(service)
            assert strategy.name == service, (
                f"Strategy name mismatch: {strategy.name!r} != {service!r}"
            )

    def test_list_supported_services_returns_10(self) -> None:
        """list_supported_services() includes all 10 MVP services."""
        supported = list_supported_services()
        assert len(supported) >= 10
        for service in MVP_SERVICES:
            assert service in supported, f"Missing from list: {service}"

    def test_case_insensitive_cancel_lookup(self) -> None:
        """Registry lookups work with mixed case."""
        assert has_strategy("Netflix")
        assert has_strategy("SPOTIFY")
        assert has_strategy("Adobe")
        assert has_strategy("Amazon Prime")
        assert has_strategy("Disney+")
        assert has_strategy("YouTube Premium")
        assert has_strategy("HULU")
        assert has_strategy("Microsoft 365")
        assert has_strategy("NordVPN")

    def test_whitespace_tolerance_cancel(self) -> None:
        """Registry lookups tolerate leading/trailing whitespace."""
        assert has_strategy("  netflix  ")
        assert has_strategy("  spotify  ")
        assert has_strategy("  amazon prime  ")


class TestAuthRegistryComplete:
    def test_all_10_auth_strategies_registered(self) -> None:
        """Every MVP service has an authentication strategy."""
        for service in MVP_SERVICES:
            assert has_auth_strategy(service), f"Missing auth strategy: {service}"

    def test_auth_strategy_instantiation(self) -> None:
        """get_auth_strategy() returns a valid instance for each service."""
        for service in MVP_SERVICES:
            strategy = get_auth_strategy(service)
            assert strategy is not None, f"get_auth_strategy returned None: {service}"

    def test_auth_strategy_names_match_keys(self) -> None:
        """Each auth strategy's .name property matches its registry key."""
        for service in MVP_SERVICES:
            strategy = get_auth_strategy(service)
            assert strategy.name == service, (
                f"Auth strategy name mismatch: {strategy.name!r} != {service!r}"
            )

    def test_auth_login_urls_not_none(self) -> None:
        """Each auth strategy defines a non-None login_url."""
        for service in MVP_SERVICES:
            strategy = get_auth_strategy(service)
            assert strategy.login_url is not None, (
                f"Auth strategy login_url is None: {service}"
            )
            assert strategy.login_url.startswith("https://"), (
                f"Auth strategy login_url not HTTPS: {service}"
            )

    def test_list_auth_supported_services_returns_10(self) -> None:
        """list_auth_supported_services() includes all 10 MVP services."""
        supported = list_auth_supported_services()
        assert len(supported) >= 10
        for service in MVP_SERVICES:
            assert service in supported, f"Missing from auth list: {service}"

    def test_case_insensitive_auth_lookup(self) -> None:
        """Auth registry lookups work with mixed case."""
        assert has_auth_strategy("Netflix")
        assert has_auth_strategy("SPOTIFY")
        assert has_auth_strategy("Adobe")
        assert has_auth_strategy("Amazon Prime")
        assert has_auth_strategy("Disney+")
        assert has_auth_strategy("YouTube Premium")
        assert has_auth_strategy("HULU")
        assert has_auth_strategy("Microsoft 365")
        assert has_auth_strategy("NordVPN")
