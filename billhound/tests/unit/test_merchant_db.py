"""Tests for merchant database category lookup."""
from __future__ import annotations

from src.services.merchant_db import lookup_category


class TestMerchantDB:
    def test_exact_match(self) -> None:
        assert lookup_category("netflix") == "streaming"
        assert lookup_category("spotify") == "music"
        assert lookup_category("nordvpn") == "vpn"

    def test_case_insensitive(self) -> None:
        assert lookup_category("Netflix") == "streaming"
        assert lookup_category("SPOTIFY") == "music"
        assert lookup_category("Adobe") == "saas"

    def test_substring_match(self) -> None:
        assert lookup_category("Netflix Premium") == "streaming"
        assert lookup_category("Adobe Creative Cloud") == "saas"

    def test_unknown_returns_none(self) -> None:
        assert lookup_category("Unknown Service XYZ") is None
        assert lookup_category("") is None

    def test_whitespace_handling(self) -> None:
        assert lookup_category("  netflix  ") == "streaming"

    def test_various_categories(self) -> None:
        assert lookup_category("google one") == "cloud_storage"
        assert lookup_category("coursera") == "education"
        assert lookup_category("grabfood") == "food_delivery"
        assert lookup_category("peloton") == "fitness"
        assert lookup_category("xbox game pass") == "gaming"
