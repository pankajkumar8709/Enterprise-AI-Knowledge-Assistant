import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeObjectType(str, enum.Enum):
    POLICY = "policy"
    EMPLOYEE = "employee"
    DEPARTMENT = "department"
    PRODUCT = "product"
    FAQ = "faq"
    BUSINESS_RULE = "business_rule"
    ASSET = "asset"


class KnowledgeObject(TimestampMixin, Base):
    __tablename__ = "knowledge_objects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    object_type: Mapped[KnowledgeObjectType] = mapped_column(
        Enum(KnowledgeObjectType, name="knowledge_object_type", values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    relations: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    object_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
