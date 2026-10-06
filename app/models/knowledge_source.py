from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeObjectSource(TimestampMixin, Base):
    """Evidence link for a knowledge object (spec §5 okf_sources).

    `quote` is verified to be a verbatim substring of the chunk text by
    `app.services.okf.validator` before insertion (spec §6.1/§7.4.4).
    """

    __tablename__ = "okf_sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    okf_object_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True
    )
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
