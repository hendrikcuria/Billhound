"""
Application-wide enums, constants, and default values.
"""
from __future__ import annotations

from enum import Enum


class BillingCycle(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    UNKNOWN = "unknown"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"
    PENDING_CONFIRMATION = "pending_confirmation"


class CancellationStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


class OAuthProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"


# Subscription categories
CATEGORIES = [
    "streaming",
    "music",
    "saas",
    "fitness",
    "gaming",
    "news",
    "cloud_storage",
    "productivity",
    "education",
    "food_delivery",
    "finance",
    "vpn",
    "other",
]

DEFAULT_CURRENCY = "MYR"
DEFAULT_TIMEZONE = "Asia/Kuala_Lumpur"
