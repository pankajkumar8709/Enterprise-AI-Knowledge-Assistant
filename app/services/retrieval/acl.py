"""Retrieval access control (spec §9.1) — single source of truth.

`acl_clause(user, model)` returns a SQLAlchemy boolean expression for any ACL
table carrying `visibility` + `department_ids` (documents, document_chunks,
knowledge_objects). The filter is applied inside the SQL query, never by
post-filtering. `admin_only` content is never returned to employees.
"""

from __future__ import annotations

from sqlalchemy import String, and_, cast, false, or_, true

from app.models.document import Visibility
from app.models.user import User, UserRole


def _department_clause(column, department_id: int | None):
    """Portable JSON int-list containment for one department id."""

    if department_id is None:
        return false()
    rendered = cast(column, String)
    marker = str(department_id)
    return or_(
        rendered == f"[{marker}]",
        rendered.like(f"[{marker}, %"),
        rendered.like(f"%, {marker}, %"),
        rendered.like(f"%, {marker}]"),
    )


def acl_clause(user: User, model):
    if user.role == UserRole.ADMIN:
        return true()
    return or_(
        model.visibility == Visibility.ALL,
        and_(
            model.visibility == Visibility.DEPARTMENT,
            _department_clause(model.department_ids, user.department_id),
        ),
    )
