"""
Factory Boy factories for Billhound models.
Used in tests to quickly create model instances.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from src.config.constants import (
    BillingCycle,
    CancellationStatus,
    SubscriptionStatus,
)
from src.db.models.audit_log import AuditLog
from src.db.models.cancellation_log import CancellationLog
from src.db.models.oauth_token import OAuthToken
from src.db.models.password_pattern import PasswordPattern
from src.db.models.subscription import Subscription
from src.db.models.user import User


def make_user(**overrides) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "telegram_id": 123456789,
        "telegram_username": "testuser",
        "display_name": "Test User",
        "is_active": True,
        "timezone": "Asia/Kuala_Lumpur",
    }
    defaults.update(overrides)
    return User(**defaults)


def make_subscription(user_id: uuid.UUID, **overrides) -> Subscription:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "service_name": "Netflix",
        "category": "streaming",
        "amount": Decimal("54.00"),
        "currency": "MYR",
        "billing_cycle": BillingCycle.MONTHLY,
        "next_renewal_date": date(2026, 4, 15),
        "status": SubscriptionStatus.ACTIVE,
        "confidence_score": Decimal("0.95"),
        "is_manually_added": False,
    }
    defaults.update(overrides)
    return Subscription(**defaults)


def make_oauth_token(user_id: uuid.UUID, **overrides) -> OAuthToken:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "provider": "gmail",
        "access_token_encrypted": "encrypted_access_token",
        "refresh_token_encrypted": "encrypted_refresh_token",
        "token_expiry": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "scopes_granted": "https://www.googleapis.com/auth/gmail.readonly",
        "email_address": "user@gmail.com",
    }
    defaults.update(overrides)
    return OAuthToken(**defaults)


def make_password_pattern(user_id: uuid.UUID, **overrides) -> PasswordPattern:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "bank_name": "Maybank",
        "pattern_description": "Last 4 digits of IC",
        "password_encrypted": "encrypted_password",
        "sender_email_pattern": "statement@maybank.com",
    }
    defaults.update(overrides)
    return PasswordPattern(**defaults)


def make_cancellation_log(user_id: uuid.UUID, **overrides) -> CancellationLog:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "service_name": "Netflix",
        "status": CancellationStatus.SUCCESS,
        "method": "automated",
        "confirmed_saving_amount": Decimal("54.00"),
        "confirmed_saving_currency": "MYR",
        "completed_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return CancellationLog(**defaults)


def make_service_credential(user_id: uuid.UUID, **overrides) -> "ServiceCredential":
    from src.db.models.service_credential import ServiceCredential

    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "service_name": "netflix",
        "username_encrypted": "encrypted_username",
        "password_encrypted": "encrypted_password",
        "auth_method": "credential",
    }
    defaults.update(overrides)
    return ServiceCredential(**defaults)


def make_extracted_subscription(**overrides) -> "ExtractedSubscription":
    from src.email_ingestion.types import ExtractedSubscription

    defaults = {
        "service_name": "Netflix",
        "amount": Decimal("54.00"),
        "currency": "MYR",
        "billing_cycle": "monthly",
        "confidence_score": 0.95,
        "source_email_subject": "Your Netflix receipt",
    }
    defaults.update(overrides)
    return ExtractedSubscription(**defaults)


def make_audit_log(**overrides) -> AuditLog:
    defaults = {
        "id": uuid.uuid4(),
        "action": "test_action",
        "details": {"key": "value"},
    }
    defaults.update(overrides)
    return AuditLog(**defaults)
