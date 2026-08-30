from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.knowledge import KnowledgeObjectType


class KnowledgeRelation(BaseModel):
    relation_type: str = Field(min_length=1, max_length=120)
    target_type: KnowledgeObjectType | None = None
    target_name: str = Field(min_length=1, max_length=255)
    evidence: str | None = Field(default=None, max_length=1000)


class KnowledgeObjectBase(BaseModel):
    object_type: KnowledgeObjectType
    name: str = Field(min_length=1, max_length=255)
    payload: dict[str, object] = Field(default_factory=dict)
    relations: list[KnowledgeRelation] = Field(default_factory=list)
    summary: str | None = Field(default=None, max_length=2000)
    source_excerpt: str | None = Field(default=None, max_length=4000)
    source_document_id: int | None = None

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

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeObjectListResponse(BaseModel):
    items: list[KnowledgeObjectRead]
    total: int


class KnowledgeExtractionResponse(BaseModel):
    document_id: int
    created: int
    updated: int
    archived: int
    items: list[KnowledgeObjectRead]
