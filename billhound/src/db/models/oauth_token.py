from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.db.models.user import User


class OAuthToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expiry: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scopes_granted: Mapped[str] = mapped_column(Text, nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)

    # Relationships
    user: Mapped[User] = relationship(back_populates="oauth_tokens")
