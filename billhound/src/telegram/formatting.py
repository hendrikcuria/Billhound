"""Message formatting utilities for Telegram messages."""
from __future__ import annotations

from decimal import Decimal

from src.config.constants import BillingCycle

_CYCLE_LABELS = {
    BillingCycle.WEEKLY: "/week",
    BillingCycle.MONTHLY: "/month",
    BillingCycle.QUARTERLY: "/quarter",
    BillingCycle.SEMI_ANNUAL: "/6 months",
    BillingCycle.ANNUAL: "/year",
    BillingCycle.UNKNOWN: "",
}

_ANNUAL_MULTIPLIERS = {
    BillingCycle.WEEKLY: 52,
    BillingCycle.MONTHLY: 12,
    BillingCycle.QUARTERLY: 4,
    BillingCycle.SEMI_ANNUAL: 2,
    BillingCycle.ANNUAL: 1,
    BillingCycle.UNKNOWN: 12,
}

_MONTHLY_DIVISORS = {
    BillingCycle.WEEKLY: Decimal("4.33"),
    BillingCycle.MONTHLY: Decimal("1"),
    BillingCycle.QUARTERLY: Decimal("3"),
    BillingCycle.SEMI_ANNUAL: Decimal("6"),
    BillingCycle.ANNUAL: Decimal("12"),
    BillingCycle.UNKNOWN: Decimal("1"),
}


def format_currency(amount: Decimal, currency: str = "MYR") -> str:
    """Format as RM1,234.00 or USD 1,234.00."""
    if currency == "MYR":
        return f"RM{amount:,.2f}"
    return f"{currency} {amount:,.2f}"


def format_billing_cycle(cycle: BillingCycle) -> str:
    """BillingCycle.MONTHLY -> '/month'."""
    return _CYCLE_LABELS.get(cycle, "")


def annualize(amount: Decimal, cycle: BillingCycle) -> Decimal:
    """Convert any billing cycle amount to annual equivalent."""
    return amount * _ANNUAL_MULTIPLIERS.get(cycle, 12)


def to_monthly(amount: Decimal, cycle: BillingCycle) -> Decimal:
    """Convert any billing cycle amount to monthly equivalent."""
    divisor = _MONTHLY_DIVISORS.get(cycle, Decimal("1"))
    if divisor == Decimal("1"):
        return amount
    return amount / divisor
