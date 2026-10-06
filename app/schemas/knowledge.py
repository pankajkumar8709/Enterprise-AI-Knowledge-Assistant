from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.document import Visibility
from app.models.knowledge import KnowledgeObjectStatus, KnowledgeObjectType

# Spec §6.2 closed predicate list; anything else is rejected (audit F-023).
RELATION_PREDICATES = frozenset(
    {
        "belongs_to",
        "manages",
        "reports_to",
        "governed_by",
        "applies_to",
        "owns",
        "part_of",
        "related_to",
        "supersedes",
    }
)


class KnowledgeRelation(BaseModel):
    relation_type: str = Field(min_length=1, max_length=120)
    target_type: KnowledgeObjectType | None = None
    target_name: str = Field(min_length=1, max_length=255)
    evidence: str | None = Field(default=None, max_length=1000)

    @field_validator("relation_type")
    @classmethod
    def validate_predicate(cls, value: str) -> str:
        if value not in RELATION_PREDICATES:
            raise ValueError(f"Unknown relation predicate '{value}'. Allowed: {', '.join(sorted(RELATION_PREDICATES))}")
        return value


class KnowledgeObjectBase(BaseModel):
    object_type: KnowledgeObjectType
    name: str = Field(min_length=1, max_length=255)
    payload: dict[str, object] = Field(default_factory=dict)
    relations: list[KnowledgeRelation] = Field(default_factory=list)
    summary: str | None = Field(default=None, max_length=2000)
    source_excerpt: str | None = Field(default=None, max_length=4000)
    source_document_id: int | None = None
    visibility: Visibility = Visibility.ALL
    department_ids: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class KnowledgeObjectCreate(KnowledgeObjectBase):
    pass


class KnowledgeObjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    payload: dict[str, object] | None = None
    relations: list[KnowledgeRelation] | None = None
    summary: str | None = Field(default=None, max_length=2000)
    source_excerpt: str | None = Field(default=None, max_length=4000)
    visibility: Visibility | None = None
    department_ids: list[int] | None = None
    # Spec §8 PATCH /knowledge/{id}: a change note is mandatory (audit F-038).
    change_note: str = Field(min_length=1, max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class KnowledgeReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class KnowledgeBulkReviewRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    action: str  # "approve" | "reject"

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in {"approve", "reject"}:
            raise ValueError("action must be 'approve' or 'reject'")
        return value


class KnowledgeObjectRead(BaseModel):
    id: int
    object_type: KnowledgeObjectType
    object_key: str
    name: str
    payload: dict[str, object]
    relations: list[KnowledgeRelation]
    summary: str | None
    source_excerpt: str | None
    schema_version: int
    object_version: int
    is_current: bool
    extraction_method: str
    source_document_id: int | None
    status: KnowledgeObjectStatus
    visibility: Visibility
    department_ids: list[int]
    confidence: float | None
    created_by_id: int | None = None
    reviewed_by_id: int | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeObjectListResponse(BaseModel):
    items: list[KnowledgeObjectRead]
    total: int
    page: int
    page_size: int


class KnowledgeExtractionResponse(BaseModel):
    document_id: int
    created: int
    updated: int
    archived: int
    dropped_invalid: int
    items: list[KnowledgeObjectRead]
