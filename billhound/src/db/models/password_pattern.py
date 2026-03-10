from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.db.models.user import User


class PasswordPattern(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "password_patterns"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_description: Mapped[str] = mapped_column(Text, nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    sender_email_pattern: Mapped[str | None] = mapped_column(String(320))

    # Relationships
    user: Mapped[User] = relationship(back_populates="password_patterns")
