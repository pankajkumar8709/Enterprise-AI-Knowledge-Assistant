"""OKF schema constants — spec §6.2 (closed lists; validated, never assumed)."""

from app.models.knowledge import KnowledgeObjectType

# Spec §6.2 required (★) and optional attributes per type.
OKF_ATTRIBUTES: dict[KnowledgeObjectType, dict[str, set[str]]] = {
    KnowledgeObjectType.POLICY: {
        "required": {"title", "summary"},
        "optional": {"effective_date", "owner_department", "version_label", "rules"},
    },
    KnowledgeObjectType.EMPLOYEE: {
        "required": {"full_name", "job_title"},
        "optional": {"department", "email", "phone", "reports_to", "location"},
    },
    KnowledgeObjectType.DEPARTMENT: {
        "required": {"name"},
        "optional": {"head", "description", "email", "location"},
    },
    KnowledgeObjectType.PRODUCT: {
        "required": {"name"},
        "optional": {"description", "category", "specs", "price", "owner_department"},
    },
    KnowledgeObjectType.FAQ: {
        "required": {"question", "answer"},
        "optional": {"category"},
    },
    KnowledgeObjectType.BUSINESS_RULE: {
        "required": {"statement", "subject"},
        "optional": {"value", "unit", "condition", "applies_to", "policy"},
    },
    KnowledgeObjectType.ASSET: {
        "required": {"name"},
        "optional": {"asset_type", "identifier", "owner", "location", "status"},
    },
}

# Spec §6.2 relation predicates (closed list).
ALLOWED_PREDICATES: frozenset[str] = frozenset(
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


def required_attributes(object_type: KnowledgeObjectType) -> set[str]:
    return OKF_ATTRIBUTES[object_type]["required"]


def predicate_is_allowed(predicate: str) -> bool:
    return predicate in ALLOWED_PREDICATES
