import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    FetchedValue,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TSVECTOR, Base, TimestampMixin
from app.models.document import JSON_TYPE, Visibility


class KnowledgeObjectType(str, enum.Enum):
    POLICY = "policy"
    EMPLOYEE = "employee"
    DEPARTMENT = "department"
    PRODUCT = "product"
    FAQ = "faq"
    BUSINESS_RULE = "business_rule"
    ASSET = "asset"


class KnowledgeObjectStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class KnowledgeObject(TimestampMixin, Base):
    __tablename__ = "knowledge_objects"
    __table_args__ = (
        # Spec §5/§6.3: exactly one live object per canonical key
        # (partial unique index over the live statuses, matching the DB).
        Index(
            "uq_knowledge_objects_live_key",
            "object_key",
            unique=True,
            postgresql_where=text("status IN ('pending_review','approved')"),
            sqlite_where=text("status IN ('pending_review','approved')"),
        ),
        # Phase 5.5 item 6 (spec §5/§9.3): OKF search indexes. The PG-specific
        # USING/ops clauses are ignored by other dialects.
        Index("ix_knowledge_objects_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_knowledge_objects_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index(
            "ix_knowledge_objects_attributes",
            "payload",
            postgresql_using="gin",
            postgresql_ops={"payload": "jsonb_path_ops"},
        ),
        Index("ix_knowledge_objects_type_status", "object_type", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    object_type: Mapped[KnowledgeObjectType] = mapped_column(
        Enum(
            KnowledgeObjectType,
            name="knowledge_object_type",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    relations: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    object_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    status: Mapped[KnowledgeObjectStatus] = mapped_column(
        Enum(
            KnowledgeObjectStatus,
            name="knowledge_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=KnowledgeObjectStatus.PENDING_REVIEW,
        nullable=False,
    )
    visibility: Mapped[Visibility] = mapped_column(
        Enum(
            Visibility,
            name="visibility",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=Visibility.ALL,
        nullable=False,
    )
    department_ids: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Phase 5.5/§9.3: search_text = name + flattened attributes, trigram-indexed on PostgreSQL.
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full-text vector over search_text. On PostgreSQL this is a GENERATED
    # ALWAYS STORED column (migration 0009), so the ORM must never send a
    # value: server_default=FetchedValue() makes INSERT emit DEFAULT, which
    # GENERATED ALWAYS columns accept. On SQLite the migration never ran,
    # so it stays a plain nullable column there.
    search_tsv: Mapped[object | None] = mapped_column(
        TSVECTOR(),
        nullable=True,
        server_default=FetchedValue(),
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
