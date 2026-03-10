"""Tests for Telegram message formatting utilities."""
from __future__ import annotations

from decimal import Decimal

from src.config.constants import BillingCycle
from src.telegram.formatting import (
    annualize,
    format_billing_cycle,
    format_currency,
    to_monthly,
)


class TestFormatCurrency:
    def test_basic_myr(self) -> None:
        assert format_currency(Decimal("54.00")) == "RM54.00"

    def test_thousands_separator(self) -> None:
        assert format_currency(Decimal("2940.00")) == "RM2,940.00"

    def test_non_myr_currency(self) -> None:
        assert format_currency(Decimal("10.00"), "USD") == "USD 10.00"

    def test_zero(self) -> None:
        assert format_currency(Decimal("0.00")) == "RM0.00"

    def test_large_amount(self) -> None:
        assert format_currency(Decimal("12345.67")) == "RM12,345.67"


class TestFormatBillingCycle:
    def test_monthly(self) -> None:
        assert format_billing_cycle(BillingCycle.MONTHLY) == "/month"

    def test_annual(self) -> None:
        assert format_billing_cycle(BillingCycle.ANNUAL) == "/year"

    def test_weekly(self) -> None:
        assert format_billing_cycle(BillingCycle.WEEKLY) == "/week"

    def test_unknown(self) -> None:
        assert format_billing_cycle(BillingCycle.UNKNOWN) == ""


class TestAnnualize:
    def test_monthly_to_annual(self) -> None:
        assert annualize(Decimal("54"), BillingCycle.MONTHLY) == Decimal("648")

    def test_annual_stays(self) -> None:
        assert annualize(Decimal("648"), BillingCycle.ANNUAL) == Decimal("648")

    def test_weekly_to_annual(self) -> None:
        assert annualize(Decimal("10"), BillingCycle.WEEKLY) == Decimal("520")

    def test_quarterly(self) -> None:
        assert annualize(Decimal("100"), BillingCycle.QUARTERLY) == Decimal("400")


class TestToMonthly:
    def test_monthly_stays(self) -> None:
        assert to_monthly(Decimal("54"), BillingCycle.MONTHLY) == Decimal("54")

    def test_annual_to_monthly(self) -> None:
        result = to_monthly(Decimal("120"), BillingCycle.ANNUAL)
        assert result == Decimal("10")

    def test_quarterly_to_monthly(self) -> None:
        result = to_monthly(Decimal("90"), BillingCycle.QUARTERLY)
        assert result == Decimal("30")
