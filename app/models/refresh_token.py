from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RefreshToken(TimestampMixin, Base):
    """Opaque refresh tokens; only the SHA-256 hash is stored (spec §5)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        # Named unique constraint to match migration 0009 (spec §5).
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
