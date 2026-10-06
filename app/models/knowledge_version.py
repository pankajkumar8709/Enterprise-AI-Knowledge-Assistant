from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.document import JSON_TYPE


class KnowledgeObjectVersion(TimestampMixin, Base):
    """Immutable snapshot per knowledge-object version (spec §5 okf_object_versions).

    The snapshot JSON holds the full OKF envelope of that version plus a
    `diff` summary when the change was an edit (spec §6.3).
    """

    __tablename__ = "okf_object_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    okf_object_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
