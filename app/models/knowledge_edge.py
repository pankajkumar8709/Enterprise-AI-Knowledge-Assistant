from sqlalchemy import Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.knowledge import KnowledgeObjectStatus


class KnowledgeObjectRelation(TimestampMixin, Base):
    """Typed directed edge between two knowledge objects (spec §5 okf_relations).

    `predicate` is restricted to the closed list in services/okf/schema.py
    (§6.2); anything else is rejected by the validator.
    """

    __tablename__ = "okf_relations"
    __table_args__ = (
        UniqueConstraint("subject_id", "predicate", "object_id", name="uq_okf_relations_subject_predicate_object"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    predicate: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[KnowledgeObjectStatus] = mapped_column(
        Enum(
            KnowledgeObjectStatus,
            name="knowledge_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=KnowledgeObjectStatus.PENDING_REVIEW,
        nullable=False,
    )
