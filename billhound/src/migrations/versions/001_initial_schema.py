"""Initial schema — all 7 tables for Billhound MVP.

Revision ID: 001
Revises:
Create Date: 2026-03-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False, index=True),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("timezone", sa.String(50), server_default="Asia/Kuala_Lumpur", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── subscriptions ─────────────────────────────────────────
    billing_cycle_enum = sa.Enum(
        "weekly", "monthly", "quarterly", "semi_annual", "annual", "unknown",
        name="billing_cycle_enum",
    )
    subscription_status_enum = sa.Enum(
        "active", "trial", "cancelled", "expired", "paused", "pending_confirmation",
        name="subscription_status_enum",
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="MYR", nullable=False),
        sa.Column("billing_cycle", billing_cycle_enum, server_default="monthly", nullable=False),
        sa.Column("next_renewal_date", sa.Date, nullable=True),
        sa.Column("trial_end_date", sa.Date, nullable=True),
        sa.Column("status", subscription_status_enum, server_default="active", nullable=False),
        sa.Column("confidence_score", sa.Numeric(3, 2), server_default="1.00", nullable=False),
        sa.Column("source_email_subject", sa.Text, nullable=True),
        sa.Column("is_manually_added", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("last_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_change_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_url", sa.Text, nullable=True),
        sa.Column("last_renewal_alert_sent_at", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── oauth_tokens ──────────────────────────────────────────
    op.create_table(
        "oauth_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=False),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes_granted", sa.Text, nullable=False),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── password_patterns ─────────────────────────────────────
    op.create_table(
        "password_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("pattern_description", sa.Text, nullable=False),
        sa.Column("password_encrypted", sa.Text, nullable=False),
        sa.Column("sender_email_pattern", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── service_credentials ───────────────────────────────────
    op.create_table(
        "service_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("username_encrypted", sa.Text, nullable=False),
        sa.Column("password_encrypted", sa.Text, nullable=False),
        sa.Column("auth_method", sa.String(20), server_default="credential", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "service_name", name="uq_user_service"),
    )

    # ── audit_log ─────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("details", JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # ── cancellation_logs ─────────────────────────────────────
    cancellation_status_enum = sa.Enum(
        "initiated", "in_progress", "success", "failed", "manual_required",
        name="cancellation_status_enum",
    )

    op.create_table(
        "cancellation_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("status", cancellation_status_enum, server_default="initiated", nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("screenshot_path", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("confirmed_saving_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("confirmed_saving_currency", sa.String(3), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cancellation_logs")
    op.drop_table("audit_log")
    op.drop_table("service_credentials")
    op.drop_table("password_patterns")
    op.drop_table("oauth_tokens")
    op.drop_table("subscriptions")
    op.drop_table("users")

    # Drop enums
    sa.Enum(name="cancellation_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="subscription_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="billing_cycle_enum").drop(op.get_bind(), checkfirst=True)
