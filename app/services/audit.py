"""Append-only audit log service (spec §11 event list, audit F-012)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

# audit_logs.entity_id is VARCHAR(80); long composite values (e.g. every id
# joined for a bulk review) must not crash the whole request with a 500.
_ENTITY_ID_MAX_LEN = 80


def _fit_entity_id(entity_id: str | None) -> str | None:
    """Shorten over-long audit entity ids to exactly the column limit."""

    if entity_id is None or len(entity_id) <= _ENTITY_ID_MAX_LEN:
        return entity_id
    suffix = f"...(+{len(entity_id)} chars)"
    head_len = max(0, _ENTITY_ID_MAX_LEN - len(suffix))
    return f"{entity_id[:head_len]}{suffix}"


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
    commit: bool = True,
) -> AuditLog:
    fitted = _fit_entity_id(entity_id)
    if fitted != entity_id:
        logger.warning("audit entity_id truncated to %d chars for action=%s", _ENTITY_ID_MAX_LEN, action)
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=fitted,
        metadata_json=metadata or {},
        ip=ip,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry
